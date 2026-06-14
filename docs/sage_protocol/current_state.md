# Current State

Last updated: 2026-06-14.

## Canonical SAGE Implementation

SAGE is the native ToolSandbox self-evolving Praxis system in this repository.
From this point forward, "SAGE" refers to the v061 evidence-line configuration:

- runner: `scripts/run_sage_protocol.py`;
- policy: `--sage-policy self-evolving-praxis`;
- actor/user/generation model: `gpt-4o-mini`;
- generation: on;
- SAGE task cache: off;
- OpenAI response cache: disabled;
- baseline/control cache: allowed when explicitly reported;
- dashboard: Task Compare;
- bridge policy: `SAGE_PRAXIS_BRIDGE_POLICY=disabled`;
- scenario-name birth/routing: disabled;
- scenario metadata policy: `SAGE_SCENARIO_METADATA_POLICY=visible_context`;
- generated-tool guidance: minimal;
- generated-tool docstrings: compact;
- generated-tool contract retry turns: `0`;
- generated-tool synthetic repair: off;
- visible-not-called retry: off;
- side-effect fair-chance extra turns: off;
- runtime generated-tool bundle cap: `4`;
- online reflection: enabled as explicit task-feedback for lifecycle decisions.

The cleaned codebase no longer includes active runtime packages for the
standalone/import-agent, CyberGym, tau, MiniGrid, or BBH experiments. Those
paths remain only as historical methodology and portability context.

## Canonical Full Dataset Evidence

- Run:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410`
- Dashboard:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/dashboard/task_compare.html`
- Protocol manifest:
  `outputs/chapter3_token_reduction/v061_finish_v059_full/online_build_full_20260613_203410/protocol_manifest.json`
- Completed paired tasks: `1032/1032`
- Score: baseline `0.733214` to SAGE `0.801186`
- Score delta/lift: `+0.067971`, `+9.27%`
- Outcome: baseline `0.454251` to SAGE `0.757267`
- Outcome delta/lift: `+0.303016`, `+66.71%`
- Exact successes: baseline `201`, SAGE `406`
- Accepted/generated tools in registry: `22`
- Called tools: `21`
- Generated-tool-called scenarios: `825`
- Tool reuse events: `1171`
- Generated-tool failures: `3`
- Runtime exceptions: `0`
- Runtime incidents: `0`
- Side-effect preservation incidents: `1`
- Baseline LLM tokens: `10,465,294`
- SAGE LLM tokens: `17,245,671`

The primary claim supported by v061 is outcome improvement through autonomous
tool generation, validation/repair, registry retention, routing/reuse, natural
tool calls, and contribution accounting. Canonical/reference score also
improved, but the strongest result is the final-task/outcome lift.

## Evidence Boundary

Primary SAGE evidence must not enable synthetic bridge completions,
route-around answer policies, hidden label access, generated tools that encode
scenario IDs or expected answers, SAGE-only extra retry turns, or scenario-name
tool birth/routing.

SAGE may use visible task text, visible tool schemas, visible tool outputs,
generated-tool validation results, official task feedback/control deltas for
online lifecycle decisions, registry metadata, and contribution/safety logs.

Generated tools are deterministic Python tools. They prepare action arguments,
normalize timestamps or units, select records from visible evidence, detect
insufficient information, recommend original tool calls, or summarize visible
evidence. Original ToolSandbox tools remain responsible for state mutation.

## Retained Code Surface

The active implementation surface is:

- `scripts/run_sage_protocol.py`
- `scripts/prepare_toolsandbox_full_self_evolving_run.py`
- `scripts/render_chapter3_sage_figures.py`
- `src/sage_ts/`
- `tool_sandbox/`
- focused `tests/unit/` and `tests/integration/`

Use `make compile`, `make test-core`, and `make test` for validation.

## Historical References

The strongest older broad500 reference remains v71:

- Run:
  `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`
- Score: `0.656799 -> 0.854188`, lift `+30.05%`
- Outcome: `0.494746 -> 0.880845`, lift `+78.04%`
- Caveat: one strict side-effect-preservation near miss on a read-only
  reminder-search task; no state mutation occurred.

The clean safety reference remains v70:

- Run:
  `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`
- Score: `0.656799 -> 0.827506`, lift `+25.99%`
- Outcome: `0.494746 -> 0.872782`, lift `+76.41%`
- Runtime/tool incidents: `0 / 0`

These older runs are retained as historical evidence, not as the current
publication configuration.
