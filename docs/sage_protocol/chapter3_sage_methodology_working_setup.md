# Chapter 3 Working Setup: SAGE Methodology And Full ToolSandbox Execution

Status: methodology working draft, not a protected final-claim artifact.

## Recommended Main Implementation

Use the ToolSandbox self-evolving Praxis implementation as the Chapter 3 primary
SAGE system.

The best current implementation is the generation-enabled ToolSandbox protocol
path:

- Runner: `scripts/run_sage_protocol.py`
- Policy preset: `--sage-policy self-evolving-praxis`
- SAGE execution path: `src/sage_ts/adapters/sage_run_adapter.py`
- ToolSandbox integration: `src/sage_ts/runtime/toolsandbox_integration.py`
- Tool generation: `src/sage_ts/generation/tool_generator.py`
- Tool validation: `src/sage_ts/validation/`
- Registry and manifests: `src/sage_ts/registry/manifest.py`
- Actor/checker bridge: `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- Dashboard: `src/sage_ts/dashboard/task_compare_template.py`

This is the implementation that most closely preserves the successful
ToolSandbox behavior: identify deterministic gaps, generate real Python generated
tools, validate and repair them, store accepted tools, route them naturally,
track gains/regressions, and retain/refine/park tools.

## Why This Implementation

The strongest ToolSandbox evidence came from full SAGE behavior, not prompt-only
guidance. The critical ingredients were:

1. Generation starts from an empty generated-tool registry.
2. Gaps are detected from visible task/trace evidence, not hidden labels.
3. Generated tools are real side-effect-free Python tools.
4. Generated tools are validated before registry acceptance.
5. Accepted tools can become visible during the same task without granting
   SAGE-only extra retry turns or force-calling tools as evidence.
6. Generated tools prepare deterministic values or final-action-ready arguments.
7. Original ToolSandbox side-effect tools still perform state changes.
8. Actor-facing generated-tool guidance improves natural adoption while
   synthetic bridge completions remain disabled for primary evidence.
9. Control baselines use task-level cache when eligible; SAGE arms run fresh.
10. Dashboards and contribution exports record whether gains are tool-driven.

## Current Evidence Boundary

The current strongest clean self-evolving broad500 ToolSandbox reproduction is:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`
- Canonical/reference: `0.656799 -> 0.854188`, delta `+0.197389`, lift `+30.05%`
- Outcome/task completion: `0.494746 -> 0.880845`, delta `+0.386099`, lift `+78.04%`
- Controls: `500 cached / 0 fresh`
- SAGE task cache: off
- OpenAI response cache: disabled
- Starting generated registry: empty/absent
- Accepted live-born tools: `16`
- Naturally called generated-tool scenarios: `297`
- Generated-tool failures: `0`
- Runtime exceptions: `0`

Caveat: one strict generated-tool-contract side-effect preservation near miss was reported
on a read-only reminder-search task. No state mutation occurred, but a protected
final claim should repair or adjudicate this before claim promotion.

The prior v70 broad500 run remains methodologically important because it had zero
generated-tool side-effect incidents:

- Run: `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`
- Canonical/reference: `0.656799 -> 0.827506`, delta `+0.170706`, lift `+25.99%`
- Outcome/task completion: `0.494746 -> 0.872782`, delta `+0.378036`, lift `+76.41%`
- Controls: `500 cached / 0 fresh`
- Accepted live-born tools: `16`
- Naturally called generated-tool scenarios: `295`
- Runtime/generated-tool incidents: `0 / 0`

## What The Portability Stress Tests Showed

The standalone/importable `sage_agent` work is valuable for future generalization,
but it is not yet the best Chapter 3 primary implementation.

Tau3 and CyberGym showed that a host-owned harness needs deep enough integration
for generated tools to affect the action loop. Prompt guidance alone is not
equivalent to full SAGE. A portable future implementation should expose:

- before-task generated-tool routing,
- before-step generated-tool rerouting,
- callable generated tools,
- pre-side-effect action review,
- same-task generated-tool availability without unfair extra turns,
- scorer-normalized feedback after the attempt,
- lifecycle accounting for gains, regressions, VNC, and retirement/refinement.

Tau3 also showed a specific framework limitation: SAGE can birth and validate
generated tools, but final-action-ready generated tools must remain prioritized
at the decisive side-effect moment. Otherwise weaker lookup/planning generated
tools crowd out the tool that would produce the actual state-changing
arguments.

For the dissertation, frame this as a portability limitation and future-work
requirement, not as the primary ToolSandbox result.

## Full ToolSandbox Execution Readiness

The code now supports a generation-enabled full-dataset ToolSandbox build mode:

- Mode: `online_build_full`
- Manifest split used: `full_benchmark`
- Manifest: `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`

This mode intentionally differs from `full_benchmark` mode. `full_benchmark`
remains frozen validation and defaults to generation off. `online_build_full`
uses the same sealed split but keeps generation on for self-evolving execution.

Preparation script:

```bash
PYTHONPATH=src:. python scripts/prepare_toolsandbox_full_self_evolving_run.py
```

This script writes a preflight report and prints the exact full-run command. It
does not launch the full run unless `--execute` is passed.

Recommended execution command:

```bash
PYTHONPATH=src:. \
TOOLSANDBOX_RAPID_CACHE_MODE=read_only \
TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json \
python scripts/run_sage_protocol.py \
  --mode online_build_full \
  --manifest docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json \
  --registry-dir artifacts/self_evolving_sage/full_toolsandbox_current/registry \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-5 \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache use-if-eligible \
  --control-cache-root artifacts/baselines/control_task_baselines \
  --routing-evidence-mode disabled \
  --freeze-toolsandbox-clock \
  --dashboard-port 62624 \
  --output-root outputs/self_evolving_sage/full_toolsandbox_current \
  --artifact-root artifacts/self_evolving_sage/full_toolsandbox_current_artifacts
```

Use `--control-cache strict` only when every control task is known to be eligible
for task-level baseline cache. Otherwise `use-if-eligible` uses cached controls
where possible and records fresh controls transparently.

## Full-Run Success Criteria

For Chapter 4 data collection, a full ToolSandbox execution should report:

- baseline cached/fresh counts,
- SAGE candidate task cache off,
- OpenAI response cache disabled,
- external RapidAPI fixture hash if used,
- model roles and resolved models,
- generated tools born/accepted/rejected/repaired,
- generated-tool visibility/calls/VNC,
- generated-tool called-subset outcome contribution,
- runtime exceptions,
- generated-tool runtime failures,
- generated-tool side-effect preservation incidents,
- score lift and outcome lift,
- task-level gains, regressions, and preserved successes/failures.

For protected final-claim language, generation-enabled results should be treated
as self-evolving discovery/methodology evidence until a frozen-registry matched
validation reproduces the result with generation off and zero safety incidents.

## Chapter 3 Recommendation

Chapter 3 should present SAGE in three layers:

1. Mature ToolSandbox SAGE: the primary system and evidence base.
2. Self-evolving Praxis treatment: the high-lift generation-enabled discovery
   mechanism used to build and evaluate generated-tool portfolios.
3. Portable import-agent work: an extension path for other benchmarks, with
   documented integration requirements and current limitations.
