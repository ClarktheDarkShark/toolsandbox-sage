# Current State

Last updated: 2026-09-10.

## Publication Release Status

The production release is the restored **policy-directed** SAGE intervention.
The July 2026 campaign remains archival development evidence, not final
inference, because its reported “v140” control was a hybrid cache and its source
tree was dirty. A later strict, fully uncached 1,032-task pair completed with
parallel fresh control and SAGE arms and no runtime exceptions. Exact v9 replay
of that pair gives audited all-task outcomes `0.586240 -> 0.779393`; the
unchanged paper-v1 endpoint on the exact ordered 800-task subset gives
`0.503964 -> 0.799612`.

Canonical/reference score is descriptive only and is not a release or paper
gate. The active validation contract uses audited v9 over all 1,032 tasks for
current same-run lift, and paper-v1 over the same 800 tasks used historically
for the historical floor/mean comparison. The final ten-pair campaign has not
started. The completed live pair predates the final v9 evaluator correction, so
its exact v9 values are an offline replay, not a clean final-tree v9 execution.
One fresh, fully uncached 1,032-task pair from the committed final tree remains
the last execution gate before the ten confirmatory pairs; no final campaign
result should be inferred from the single engineering sample.

## Canonical SAGE Implementation

SAGE is the native ToolSandbox self-evolving Praxis system in this repository.
For the publication release, "SAGE" refers to the policy-directed production
configuration:

- runner: `scripts/run_sage_protocol.py`;
- policy: `--sage-policy self-evolving-praxis`;
- actor selection: deterministic policy cascade with named `tool_choice` where
  the policy covers the step;
- actor/user/generation model: `gpt-4o-mini`;
- generation: on;
- SAGE task cache: off;
- persistent repository whole-response replay cache: disabled (provider prompt-prefix
  computation is a distinct OpenAI-managed mechanism);
- baseline/control cache: historically allowed when explicitly reported, but
  prohibited in new publication runs;
- execution: fresh non-learning control and SAGE run concurrently, with the
  matching control row streamed to SAGE at each task boundary;
- dashboard: Task Compare, externally opened before model execution;
- synthetic bridge completions: removed from the active runtime;
- scenario-name birth/routing: disabled;
- gap detection and routing use visible task text, tool schemas, and tool results;
- generated-tool guidance: minimal;
- generated-tool docstrings: compact;
- runtime generated-tool bundle cap: `4`;
- online reflection: enabled with post-task evaluator-derived scalar feedback;
  paper-v1 supplies the signal on 800 tasks and audited v9 is the fallback on
  the other 232. Raw benchmark targets are not exposed to the actor or generated
  tools during the task.

The sections below preserve dated development results for provenance. Their
natural-selection descriptions and older evaluator numbers are not statements
of the current production intervention or directly comparable final metrics.

## Validated Production Cleanup Checkpoint (2026-08-02 Historical)

At that checkpoint, the non-dashboard `src/sage_ts` production surface was 43,545 Python
lines across 53 files. The 2026-08-02 optional-branch cleanup removed another
2,651 net lines (2,766 deletions and 115 additions) without changing dashboard
source.

Deterministic checks matched the pre-cleanup checkpoint exactly across all
1,032 tasks and 1,810 classifier observations, generation prompts, and repair
prompts. Three independent 30-task validation cohorts passed their fixed
pre-cleanup floors. The final 1,032-task run completed with:

- score: `0.733488 -> 0.798621`, lift `+8.88%`;
- outcome: `0.457342 -> 0.789970`, lift `+72.73%`;
- accepted tools: `30`;
- policy-selected generated tools/scenarios: `29 / 768`;
- reuse events: `1,878`;
- runtime exceptions: `0`;
- harmful side-effect incidents after audit: `0`.

The score was slightly above the protected ten-run mean of `0.797953`. Outcome
was 0.48 standard deviations below the protected mean of `0.795407` and inside
the observed `0.776052-0.809509` range. This passes the distributional
no-degradation gate; it does not claim deterministic reproduction of the
stronger 0.807327 single run.

Run:
`outputs/production_cleanup_20260802/full_optional_cleanup_equivalence_20260802_172055/online_build_full_20260802_172101`

Report:
`docs/sage_protocol/production_optional_branch_cleanup_20260802.md`

Gate:
`artifacts/production_cleanup_20260802/optional_branch_cleanup_gate.json`

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

The primary historical claim supported by v061 concerned outcome improvement
through autonomous tool generation, validation/repair, registry retention,
routing/reuse, natural tool calls, and contribution accounting. That
natural-selection configuration is not the restored policy-directed production
intervention and is retained here only as historical evidence.

## Native-Action SAGE Status

The leading completed full-dataset outcome run in July was:

- Run:
  `outputs/native_action_4omini_ab/full_outcome80_finite_domain_full_20260723_114932/native_action/online_build_full_20260723_114954`
- Score: `0.733488 -> 0.797695`, lift `+8.75%`.
- Composite outcome: `0.457342 -> 0.800043`, lift `+74.93%`.
- Exact outcome successes: `161 -> 441`.
- State checks: `0.712231 -> 0.906944`; exact `510 -> 653`.
- Answer checks: `0.405415 -> 0.706502`; exact `134 -> 297`.
- Generated-tool-called rows: `771`, with outcome
  `0.373165 -> 0.809496` (`+116.93%`).
- Runtime exceptions: `0`.

The historical run used model-authored `gpt-4o-mini` generation and repair, an
empty starting registry, visible task text and schemas, validation, registry
reuse, generated-tool calls, and native actions. Bridge behavior, scenario-name birth and
routing, diagnostic force calls, persistent repository whole-response replay, SAGE task caching,
and SAGE-only extra actor turns were disabled.

The framework now exposes finite input values declared by generated code as
call-schema enums and projects generated action sequences onto native actions
available in the current tool surface. This is a generated-tool interface
method, not a task-name or answer-specific rule.

The strongest descriptive association is that generated-tool-called rows had
the largest lift. Rows with no visible generated tool were effectively tied
with the baseline, and visible-but-not-called rows regressed. Because tool-call
status is selected after treatment, this subset does not by itself establish
that the generated call caused the outcome; that would require an ablation.

The run recorded 43 failed tool calls: 42 from
`apply_single_device_state_action` and one from `extract_distance_result`.
There was one side-effect-preservation contract flag for the generated device
sequence planner. It reflected an unexecuted final planned action at the turn
limit, not a prohibited mutation; the preceding state changes were valid.
These are the primary reliability issues for the next iteration.

This native-action configuration was the leading outcome-focused candidate in
July. It is now a historical reference pending the corrected-tree validation and
fresh-control campaign described above. A separate standard-SAGE arm would still
be required to claim broad
superiority over the prior SAGE implementation itself rather than over the
non-learning baseline.

## Five-Run Native-Action Replication

Five independent full-dataset replications of that July native-action
configuration completed in parallel:

- Batch:
  `outputs/chapter4_current_sage_replications/current_sage_rep5_20260723_220047`
- Completed paired tasks: `5 x 1,032`; all five protocol gates passed.
- Shared baseline: score `0.733488`; outcome `0.457342`.
- Mean SAGE score: `0.794218`; mean score delta/lift:
  `+0.060730 / +8.28%`.
- Mean SAGE outcome: `0.798905`; mean outcome delta/lift:
  `+0.341563 / +74.68%`.
- SAGE outcome range: `0.778770` to `0.809509`; run-level SD `0.012084`.
- Run-level 95% t interval for mean SAGE outcome:
  `[0.783900, 0.813909]`.
- Two-way run/task bootstrap 95% interval for outcome delta:
  `[+0.309375, +0.374102]`.
- Three of five replications reached outcome `>= 0.8`; all five exceeded
  `+50%` outcome lift.
- Generated-tool-called scenario-runs: `3,856`; their weighted outcome was
  `0.380854 -> 0.806497`, delta `+0.425643`, lift `+111.76%`.
- Accepted tools: mean `28.4` per run; total reuse events `9,290`.
- Runtime exceptions/tool runtime incidents: `0 / 0`.
- Generated-tool failed scenarios: `177`, of which `164` came from
  `apply_single_device_state_action`.
- Side-effect-preservation contract flags: `4`, all involving
  `plan_device_state_action_sequence_v3`; these remain explicit safety
  adjudication items.

Analysis-ready exports and inferential statistics are in:

`artifacts/chapter4_current_sage_replications/current_sage_rep5_20260723_220047/aggregate`

## Evidence Boundary

Primary SAGE evidence must not enable synthetic bridge completions, hidden label
access, generated tools that encode scenario IDs or expected answers, SAGE-only
extra retry turns, scenario-name tool birth/routing, or diagnostic force-call
environment variables. The restored actor policy's deterministic selector,
schema filtering, and named `tool_choice` are part of the disclosed treatment;
they are not diagnostic calls and cannot be described as natural model choice.

SAGE may use visible task text, visible tool schemas, visible tool outputs,
generated-tool validation results, post-task evaluator-derived scalar
feedback/control deltas for online lifecycle decisions, registry metadata, and
contribution/safety logs. Evaluators use benchmark answer/state targets, but the
actor and generated tools do not receive those raw targets during the task.

Generated tools are deterministic Python tools. They prepare action arguments,
normalize timestamps or units, select records from visible evidence, detect
insufficient information, recommend original tool calls, or summarize visible
evidence. Original ToolSandbox tools remain responsible for state mutation.

## Retained Code Surface

The active implementation surface is:

- `scripts/run_sage_protocol.py`
- `scripts/run_native_action_4omini_ab.sh`
- `scripts/verify_publication_environment.py`
- `scripts/verify_publication_inputs.py`
- `scripts/verify_publication_run.py`
- `scripts/run_chapter4_evidence_campaign.py`
- `src/sage_ts/` reusable SAGE core
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
