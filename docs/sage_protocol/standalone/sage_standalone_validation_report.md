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

### ToolSandbox 20-Task Baseline Correction

Date: 2026-05-20

A later 20-task `toolsandbox-probe` smoke exposed an easy-to-misread dashboard
result: the adapter smoke baseline showed `0/20`, while SAGE showed `20/20`.
That baseline was not a ToolSandbox control arm. It was only the standalone
adapter's no-helper lifecycle baseline, so it cannot be used as benchmark lift
or as evidence that the real ToolSandbox baseline solved zero tasks.

The smoke runner and standalone dashboard were updated so adapter smoke
baselines are marked with:

- `comparison_valid: false`
- `comparison_note: Standalone adapter smoke baseline only...`

The dashboard now labels these as `Probe baseline` and suppresses absolute and
relative lift. This prevents a lifecycle probe from being mistaken for a
matched ToolSandbox comparison.

A real ToolSandbox 20-task verification manifest was prepared from the first
20 tasks of the formal500 manifest:

- manifest: `artifacts/sage_standalone/toolsandbox_verify20_manifest.json`
- manifest SHA-256:
  `f1e299f46490c92d8492ab9d3f9214d837488b04bd12031c7cc3a2cc5be51170`

The matched ToolSandbox verification command was first attempted with
`scripts/run_sage_protocol.py`, generation enabled, `gpt-4o-mini`, candidate
cache off, OpenAI response cache disabled, routing evidence disabled, and
control cache eligible. It stopped before task execution because
`OPENAI_API_KEY` was missing or blank in the shell environment.

The local project secret loader was then found at `.secrets/env.sh`. The key was
confirmed present after sourcing that file without printing the secret value.
The same ToolSandbox 20-task verification was rerun from the fixed manifest:

```bash
set -a
source .secrets/env.sh
set +a
PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode mechanism_40 \
  --manifest artifacts/sage_standalone/toolsandbox_verify20_manifest.json \
  --generation on \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --disable-openai-response-cache \
  --cache-mode off \
  --parallel-arms \
  --control-cache use-if-eligible \
  --routing-evidence-mode disabled \
  --allow-low-quality-cohort \
  --output-root outputs/sage_agent_standalone/toolsandbox_real_verify20 \
  --artifact-root artifacts/sage_standalone/toolsandbox_real_verify20_artifacts \
  --dashboard-port 62630
```

Run root:

`outputs/sage_agent_standalone/toolsandbox_real_verify20/mechanism_40_20260520_204549/`

Dashboard:

`outputs/sage_agent_standalone/toolsandbox_real_verify20/mechanism_40_20260520_204549/dashboard/task_compare.html`

Result:

- matched tasks: `20`
- model: `gpt-4o-mini` for agent, user, and generation
- generation: on
- OpenAI response cache: disabled
- candidate/SAGE task cache: off
- routing evidence: disabled
- control-cache mode: `use-if-eligible`
- control source: mixed
- cached control tasks: `12`
- fresh control tasks: `8`
- cache manifest hash:
  `00546ff4d26e2ecd4ac595282c8a4d6d819f2e77eb7726268d835229d16243b2`
- cache misses: the 8 fresh controls had fewer than 3 compatible completed
  cached controls under the task-name/model/user/base-tool-policy rule
- baseline score: `0.7234176544455837`
- SAGE score: `0.7533925850552543`
- score delta: `+0.029974930609670648`
- baseline outcome: `0.5102649992954722`
- SAGE outcome: `0.4726350586220871`
- outcome delta: `-0.03762994067338511`
- exact successes: control `6`, SAGE `8`
- runtime exceptions: `0`
- protocol gate: failed
- gate reasons: `non_positive_outcome_delta`,
  `outcome_gains_do_not_exceed_regressions`

Interpretation: this is a real ToolSandbox matched 20-task verification run,
not an adapter smoke. It used the baseline cache to the maximum extent allowed
by the current eligibility policy: 12 cached controls and 8 fresh controls. The
run does not validate the standalone SAGE slice as ToolSandbox-ready because
the primary outcome metric regressed despite a positive canonical/score delta
and two more exact successes. The next ToolSandbox validation should either use
a manifest whose baseline tasks are fully cache-eligible or first populate
eligible control-cache records for the missing reminder/holiday tasks, then
rerun only the SAGE arm comparison against cached controls.

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

CyberGym setup audit for this dashboard:

- execution mode: `cybergym_synthetic_probe`
- benchmark-ready: `false`
- available adapter tasks: `10` published subset IDs
- real CyberGym task generation: `false`
- real PoC submission server: `false`
- real verifier-backed scoring: `false`
- `cybergym_data/data`: not present locally
- `cybergym-server-data`: not present locally

Interpretation: the `5/5` result is a useful standalone SAGE portability smoke,
but it is not evidence that SAGE solved CyberGym benchmark tasks. A 40-task
CyberGym run was intentionally not started from this setup because the current
adapter exposes only 10 synthetic/probe tasks and lacks downloaded CyberGym
task data, server data, generated task directories, PoC submission, and real
verifier scoring.

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

## CyberGym Live Submit Smoke

Date: 2026-05-20

Setup:

- downloaded the official 10-task Level 1 task assets from
  `sunblaze-ucb/cybergym` using selective Hugging Face patterns;
- generated task directories with `python3 -m cybergym.task.gen_task`;
- used `external/cybergym/mask_map.json` so generated `submit.sh` scripts
  expose masked task IDs;
- installed CyberGym server extras and launched the local `/submit-vul` server;
- pulled vulnerable runner Docker images task-by-task to avoid filling disk;
- stopped the largest pull once when disk reached unsafe levels, removed
  already-used runner images, then pulled the final runner and reran from the
  server-side deterministic submission cache plus the live final task.

Command:

```bash
PYTHONPATH=src:. python scripts/run_cybergym_live_sage.py \
  --ignore-missing-images \
  --reset-registry \
  --registry-dir artifacts/cybergym_live_sage/official10_level1_registry_10of10 \
  --output-root outputs/cybergym_live_sage \
  --run-id official10_level1_live_submit_vul_10of10 \
  --max-candidates 6
```

Dashboard:

`outputs/cybergym_live_sage/official10_level1_live_submit_vul_10of10/dashboard/index.html`

Result:

- environment: `cybergym-live`
- execution mode: `cybergym_live_level1_submit_vul`
- tasks seen: `10`
- baseline policy: fixed four-byte PoC
- baseline success: `2/10`
- SAGE success: `2/10`
- absolute lift: `+0.0 pp`
- relative lift: `+0.0%`
- gaps observed: `1`
- tools born: `1`
- tools accepted: `1`
- tools reused: `10`
- runtime/integrity issues: `0`
- skipped tasks: `0`
- lifecycle decision: `refine`

Interpretation: this is the first real CyberGym submit-path run for standalone
SAGE, not a synthetic probe. The baseline was stronger than expected because a
fixed four-byte PoC triggered vulnerable execution failures on two official
Level 1 subset tasks. The generated SAGE helper was mechanically valid and
naturally reused, but it did not improve over baseline. The result shows that
the portable SAGE loop can connect to CyberGym's real task generation and
submission machinery, but the cyber helper itself is not yet strong enough.
The next work should target source unpacking, harness discovery, format-aware
input synthesis, crash-log interpretation, and adaptive mutation/minimization.

Limitation: this run used `/submit-vul` only. It did not run fix-side
re-verification, so it remains a live smoke and must not be treated as final
CyberGym benchmark evidence.

## CyberGym Batched Live Submit Smoke

Date: 2026-05-21

Purpose: verify that the standalone SAGE adapter can operate in a new
environment in bounded batches without keeping all downloaded task data and
Docker images on disk at once. This rerun used the generic
`visible_text_candidate_planner` helper family rather than the earlier
CyberGym-shaped seed planner.

Command:

```bash
PYTHONPATH=src:. python scripts/run_cybergym_live_batched_sage.py \
  --limit 20 \
  --batch-size 4 \
  --reset-registry \
  --registry-dir artifacts/cybergym_live_sage/batched20_registry_generic_visible_v2 \
  --output-root outputs/cybergym_live_sage \
  --run-id batched20_generic_visible_v2_20260521_102125 \
  --max-candidates 24
```

Dashboard:

`outputs/cybergym_live_sage/batched20_generic_visible_v2_20260521_102125/dashboard/index.html`

Result:

- environment: `cybergym-live`
- execution mode: `cybergym_live_level1_submit_vul_batched`
- tasks requested/run: `20/20`
- batch size: `4`
- baseline policy: fixed four-byte PoC per task
- baseline success: `1/20`
- SAGE success: `4/20`
- absolute lift: `+15.0 pp`
- relative lift: `+300.0%`
- gaps observed: `17`
- tools born: `1`
- tools accepted: `1`
- tools reused: `20`
- retained-helper refinements accepted: `0`
- lifecycle decision: `refine`
- integrity issues: `0`
- skipped tasks: `0`

Interpretation: this run confirms the batched live CyberGym wiring and shows a
small real submit-path lift over the fixed-PoC control. It is still not final
CyberGym benchmark evidence because it uses `/submit-vul` only and does not run
fix-side verification. The single generic visible-text candidate planner was
accepted and reused naturally. It improved live task completion from `5%` to
`20%` on this 20-task ordered sample without hard-coding CyberGym task IDs,
expected answers, labels, task-specific strings, or reference PoCs into the
helper. The helper uses visible descriptions, visible instructions, bounded
visible source-artifact summaries, prior submit feedback, and a small universal
edge-case candidate set.

This is a meaningful portability result, but the lifecycle decision remains
`refine`: the helper helped on four tasks and failed on sixteen. The next
framework work should give SAGE richer environment-observation and repair
loops, especially source/harness inventory, input-format inference, feedback
classification, targeted mutation, and candidate minimization. Those should be
implemented as environment-general capabilities with CyberGym as one validation
target, not as task-ID or label-specific logic.

Resource cleanup check: after the run, no `n132/arvo:*` or
`cybergym/oss-fuzz:*` runner images remained listed by Docker. Batch work
directories were cleared unless explicitly retained.

## ToolSandbox Root-Cause Backtrace to the Working Self-Evolving System

Date: 2026-05-20

Question: why did the standalone ToolSandbox verify20 run regress on outcome
when the previous self-evolving SAGE runs produced very large lift?

Root cause: the failed verify20 run enabled generic generation, but did not
enable the full self-evolving Praxis runtime stack that produced the broad500
success. The prior high-lift runs were not just "generation on." They combined
just-in-time proactive helper birth, same-task fair chance for newly accepted
helpers, Praxis actor bridge policy, V2 contract/repair/dependency generation
features, safe-abstain birth, transient scenario retries, routing evidence
disabled, fresh SAGE/candidate execution, and strict cached controls.

Correct prior reference runs:

- highest clean committed-tree reproduction:
  `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`
- strongest zero-side-effect JIT same-task proof:
  `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`

Reference v71 result:

- score: `0.656799 -> 0.854188`, delta `+0.197389`
- outcome: `0.494746 -> 0.880845`, delta `+0.386099`
- exact successes: `20 -> 288`
- controls: `500 cached / 0 fresh`
- generated registry: `16` accepted helpers, `14` naturally called
- gate: pass

Reference v70 result:

- score: `0.656799 -> 0.827506`, delta `+0.170706`
- outcome: `0.494746 -> 0.872782`, delta `+0.378036`
- exact successes: `20 -> 287`
- controls: `500 cached / 0 fresh`
- generated registry: `16` accepted helpers, `14` naturally called
- helper side-effect incidents: `0`
- gate: pass

Failed standalone verify20 result:

- run: `outputs/sage_agent_standalone/toolsandbox_real_verify20/mechanism_40_20260520_204549`
- score: `0.723418 -> 0.753393`, delta `+0.029975`
- outcome: `0.510265 -> 0.472635`, delta `-0.037630`
- exact successes: `6 -> 8`
- controls: `12 cached / 8 fresh`
- generated registry: `11` accepted helpers, only `2` naturally called
- gate: fail

The behavioral failure was adoption and routing, not tool absence. The failed
run generated many familiar helpers, but most of the important helpers were
hidden or visible-not-called. The high-lift runs routed and adopted the same
types of helpers broadly: device-state action planning, search-window
resolution, contact lookup/update planning, reminder argument preparation,
message recency selectors, weekday timestamp conversion, and safe abstention.

Code repair: `scripts/run_sage_protocol.py` now has a first-class
`--sage-policy self-evolving-praxis` preset. The preset applies and records the
same policy defaults used by the successful broad500 runs:

- `SAGE_SELF_EVOLVING_PROACTIVE_BIRTH=1`
- `SAGE_SELF_EVOLVING_PROACTIVE_SCOPE=just_in_time`
- `SAGE_SELF_EVOLVING_BIRTH_SCENARIO_FAIR_CHANCE=1`
- `SAGE_ENABLE_SAFE_ABSTAIN_BIRTH=1`
- `SAGE_PRAXIS_BRIDGE_POLICY=combined`
- `SAGE_TS_TRANSIENT_SCENARIO_RETRY_ATTEMPTS=4`
- `SAGE_V2_EXPERIMENT_FEATURES=contract_synthesis,candidate_repair,dependency_logic,medium_grain_skills`
- `SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS=120`
- `SAGE_EXPERIMENTAL_CONTROL_CACHE_TASK_ONLY=1`

The preset does not overwrite explicit environment values. If a value is
already set, the protocol manifest records that it came from the preexisting
environment.

Small validation after repair:

```bash
PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode mechanism_40 \
  --manifest artifacts/sage_standalone/toolsandbox_verify20_manifest.json \
  --generation on \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache strict \
  --routing-evidence-mode disabled \
  --allow-low-quality-cohort \
  --output-root outputs/sage_agent_standalone/toolsandbox_verify20_self_evolving_policy \
  --artifact-root artifacts/sage_standalone/toolsandbox_verify20_self_evolving_policy_artifacts \
  --dashboard-port 62630
```

Run:
`outputs/sage_agent_standalone/toolsandbox_verify20_self_evolving_policy/mechanism_40_20260520_210531`

Machine-readable summary:
`artifacts/sage_standalone/toolsandbox_self_evolving_policy_backtrace_summary.json`,
SHA-256 `3bc290fa823fb832ee024466147633e7b5b4f771143a081bbb275042db6fd112`

Result:

- matched tasks: `20`
- controls: `20 cached / 0 fresh`
- score: `0.728002 -> 0.908119`, delta `+0.180117`
- outcome: `0.454649 -> 0.920139`, delta `+0.465490`
- exact successes: `3 -> 16`
- gains/regressions: `14 / 2`
- outcome gains/regressions: `14 / 1`
- generated registry: `12` accepted helpers, `8` naturally called
- runtime exceptions: `0`
- helper side-effect preservation reports: none emitted
- gate: pass

Interpretation: the previous failure was a harness/policy integration error in
the broad standalone ToolSandbox validation path. Once the high-lift
self-evolving stack is applied as a named preset, the same 20-task slice moves
from outcome regression to large positive outcome lift while starting from an
empty generated-tool registry and using only cached controls for the baseline.
This does not by itself replace the prior broad500 evidence, but it verifies
that the broader runner can activate the working SAGE mechanics.
