# SAGE: Self-Adaptive Generative Evolution

SAGE is a self-evolving agent research system. It starts from an intentionally incomplete but fair base toolset, detects missing deterministic capabilities during tasks, generates small typed Python helper tools, validates those helpers, stores accepted helpers in a persistent registry, and later routes retained helpers back into new tasks. ToolSandbox remains the primary benchmark used for the mature evidence base, and the standalone `sage_agent` package is the current path for making the same process portable across environments.

The research claim is not simply “better tool calling.” The claim is tool evolution:

1. the base toolset is inadequate for a repeated deterministic subproblem,
2. SAGE detects that inadequacy with an explicit adequacy gate,
3. SAGE generates a reusable helper tool rather than a one-off script,
4. the helper passes held-out semantic validation and runtime smoke checks,
5. the helper is retained in a local registry,
6. later tasks load and call that retained helper,
7. matched control/SAGE runs show task-outcome improvement or preservation from reuse.

This repository is built from Apple’s ToolSandbox benchmark and now also contains a development-stage environment-neutral SAGE package. The upstream ToolSandbox code, license, and benchmark README are retained below for attribution and reproducibility.

## Current Main System: SAGE Praxis With True Self-Evolution

SAGE Praxis with true self-evolution working is the current main SAGE system going forward for methodology writing and future validation campaigns. In this mode, SAGE can start from an empty generated-tool registry, keep generation on during candidate runs, identify unsupported task buckets from online gap evidence, generate and validate new helpers, retain useful tools, park harmful tools, and reuse retained helpers through system-driven routing.

For ToolSandbox protocol runs, `scripts/run_sage_protocol.py` now resolves `--sage-policy auto` to the audited high-lift `self-evolving-praxis` preset whenever generation is enabled, and to `none` for frozen validation arms. This prevents generation-enabled mechanism/build runs from accidentally exercising the weaker generic path. Use `--sage-policy none` only for explicit ablations.

This is a current-system and methodology marker, not an automatic protected final-claim update. Protected claims still require locked matched validation, zero helper side-effect incidents, documented cache policy, and protected-claim review.

Chapter 3 figure assets are available under `docs/sage_protocol/figures/` and are indexed in `docs/sage_protocol/chapter3_methodology_figures.md`. Regenerate them with:

```bash
python3 scripts/render_sage_methodology_diagrams.py
```

## What SAGE Adds

SAGE sits around the ToolSandbox execution loop rather than replacing it. The benchmark still provides the stateful environment, user simulator, tool calls, trajectories, and canonical milestone scoring. SAGE adds the experimental layer for autonomous helper-tool evolution.

- **Adequacy gate:** decides whether a task failure reflects a missing deterministic capability, repeated transform, raw-data-to-derived-value gap, or insufficient information that should not trigger tool generation.
- **Tool generation:** creates small typed Python helpers for canonicalization, timestamp/date computation, record selection/ranking, state-precondition next actions, and argument preparation.
- **Validation:** checks generated helpers with AST safety rules, import/compile checks, schema checks, semantic held-out cases, and ToolSandbox runtime smoke tests before registry insertion.
- **Persistent registry:** stores accepted helper code, metadata, validation evidence, source scenario, reuse counts, known failure modes, and registry lock/digest data.
- **Runtime routing:** exposes retained helpers only when task-stratum and helper-family triggers indicate relevance, then logs visible tools, called tools, filtered tools, and selection outcomes.
- **Evaluation harness:** runs matched control and SAGE cohorts with shared scenario order, model, base tools, cache policy, and dashboard artifacts.
- **Dashboard:** exports live run state, task transcripts, tool births, accepted/rejected helpers, registry contents, canonical score, outcome-score sanity checks, cache status, and blockers.
- **Caching and API safeguards:** uses exact OpenAI response caching for development runs and local RapidAPI caching for fixed external lookup results, while keeping claim runs cache-symmetric and explicitly reported.

Generated helpers are not allowed to be hidden-answer checkers, advisory prose plans, broad natural-language wrappers, one-off scenario patches, or replacements for ToolSandbox side-effect tools when canonical milestones require those original tools. Helpers should prepare arguments, normalize values, choose records, compute deterministic values, or return one benchmark-compatible next tool call.

## SAGE Command Surface

Common commands used during the ToolSandbox SAGE campaign:

```bash
make test
make dashboard
make reproduce_poc CACHE_MODE=read_write
make transfer_recency REGISTRY=<path> CACHE_MODE=write_only
make transfer_relative_time REGISTRY=<path> CACHE_MODE=write_only
make smoke4 CATEGORY=<category> REGISTRY=<path> CACHE_MODE=read_write
make viability12 CATEGORY=<category> REGISTRY=<path> CACHE_MODE=read_write
make transfer60 CATEGORY=<category> REGISTRY=<path> CACHE_MODE=write_only
make confirm100 REGISTRY=<path> MODE=<control|evolve> CACHE_MODE=write_only
make summarize RUN=<path>
make cache_stats RUN=<path>
make freeze_registry REGISTRY=<path> OUT=<lockfile>
```

Local secrets should be kept out of Git. Use `.secrets/` or environment variables for keys such as `OPENAI_API_KEY` and `RAPID_API_KEY`; `.secrets/` is ignored by Git.

## Importable Standalone SAGE Package

SAGE now has a development-stage standalone package boundary:

```python
from pathlib import Path

from sage_agent import SAGEAgent, SAGEConfig
from sage_agent.generators import TemplateHelperGenerator

agent = SAGEAgent(
    adapter=my_environment_adapter,
    generator=TemplateHelperGenerator(),
    config=SAGEConfig(model="gpt-4o-mini", registry_dir=Path("my_sage_registry")),
)
summary = agent.run(limit=20)
```

For benchmarks that already own the simulator, scorer, task runner, and agent
loop, use import-agent mode instead of rewriting the benchmark as a full SAGE
adapter. The host harness stays in charge of execution; SAGE only supplies
before-task guidance and consumes after-task official observations:

```python
from pathlib import Path

from sage_agent import (
    EnvironmentProfile,
    ImportTaskContext,
    ImportTaskObservation,
    SAGEImportAgent,
    SAGEImportConfig,
)
from sage_agent.generators import OpenAIHelperGenerator

profile = EnvironmentProfile(
    name="my-benchmark",
    description="Host-owned simulator, scorer, and task runner.",
    base_tools=("host_agent_loop", "official_scorer"),
    helper_families=("prompt_guidance_helper", "action_planning_helper"),
    safety_rules=("Use only visible task context and official observations.",),
)

sage = SAGEImportAgent(
    environment_profile=profile,
    registry_dir=Path("artifacts/my_benchmark_sage_registry"),
    generator=OpenAIHelperGenerator(),
    config=SAGEImportConfig(model="gpt-4o-mini", retry_policy="next_task_only"),
)

task_context = ImportTaskContext(
    task_id=task.id,
    name=task.name,
    prompt=task.visible_prompt,
    artifacts={"readme_excerpt": task.visible_readme},
    metadata={"split": "dev-visible"},
)

guidance = sage.before_task(task_context)
host_result = run_existing_harness_task(
    task,
    agent_system_prompt_extra=guidance.system_prompt,
)

sage.after_task(
    task_context,
    ImportTaskObservation(
        success=host_result.success,
        score=host_result.score,
        transcript=tuple(host_result.visible_messages),
        error=host_result.error,
    ),
)
```

Import-agent mode treats guidance as a first-class helper type. Retained
helpers may be deterministic callables, prompt-guidance helpers, action-planning
helpers, or scorer-feedback repair helpers, and all receive the same visibility,
reuse, success, retirement, validation, and registry metadata. The import layer
also exposes `paired_task_order(...)` so a host harness can keep baseline and
SAGE task order fixed. `retry_policy="same_task"` may be used only when the
host benchmark permits a clean same-task retry after helper birth; otherwise use
`next_task_only` for standard paired comparisons.

Import-agent mode treats infrastructure failures differently from task failures.
Runner exceptions, parser errors, subprocess timeouts, Docker failures,
authentication failures, and other harness problems are recorded as diagnostics
and emit `tool_birth_skipped`; they do not birth reusable helpers. This guard was
added after tau2 showed that a runner-side `JSONDecodeError` could otherwise
create irrelevant prompt guidance and pollute later tasks.

The standalone package lives in `src/sage_agent/`. It is intentionally
environment-neutral: the core SAGE controller does not know about ToolSandbox,
CyberGym, MiniGrid, contacts, reminders, PoC submission, Docker, grid worlds,
or benchmark-specific labels. Environments provide adapters that expose tasks,
normalized run results, gap signals, validation cases, helper routing, and
safety rules. Generic gap mining is enabled by default in `SAGEConfig`; it can
split one failed task into multiple reusable hypotheses when visible evidence
supports them, such as candidate-input planning from visible artifacts,
execution-feedback mutation, structured-format input planning, or grid
navigation planning. For source-artifact environments, SAGE can also generate
source-boundary candidate planners that mine visible source summaries for
magic literals, parser tokens, numeric boundaries, and comparison constants
without seeing hidden solutions or reference inputs.
CyberGym is currently used as the stress test for source-artifact,
candidate-submission behavior, but the repairs are kept in the generic SAGE
loop: adaptive candidate-portfolio planning, format-edge planning,
evidence-gated repair, same-task retry after helper birth, stopping same-task
gap mining after a successful retry, and a per-task helper-birth budget.
Those controls are not CyberGym rules; they apply to any future adapter that
surfaces visible artifacts, execution feedback, validation cases, and helper
families through the standalone interface.

Research-integrity checks are enforced at the standalone boundary. Adapters may
privately score tasks, but SAGE-facing task specs, gap signals, and helper
candidates must not expose hidden labels, expected answers, oracle fields,
answer keys, protected solutions, prior SAGE traces, or cache shortcuts. If an
adapter exposes leak-prone metadata such as `expected_answer`, `ground_truth`,
`oracle`, or `solution`, `SAGEAgent.run()` fails before generation begins.
Visible environment information remains allowed: prompts, visible files,
allowed tools, public task metadata, tool traces, and synthetic validation cases
needed to test helper robustness.

Current adapter proof points:

- `sage_agent.adapters.ToolSandboxMiniAdapter`: low-cost ToolSandbox-shaped
  smoke proof for helper birth, validation, registry storage, and reuse.
- `sage_agent.adapters.ToolSandboxScenarioProbeAdapter`: reads the real
  ToolSandbox scenario registry and validates standalone SAGE against real
  scenario names, categories, and allowed-tool surfaces without running a full
  paired benchmark.
- `sage_agent.adapters.CyberGymAdapter`: low-cost CyberGym-shaped smoke proof
  against the locally cloned `external/cybergym` repository and the published
  10-task subset IDs. It validates the adapter boundary without downloading the
  large CyberGym datasets or running a Docker PoC server.
- `sage_agent.adapters.CyberGymLiveSubmitAdapter`: real CyberGym Level 1
  submit-path adapter. It downloads visible task assets in bounded batches,
  generates task directories with CyberGym's own generator, submits candidate
  PoCs through the task `submit.sh` scripts, and records verifier-backed
  success from `/submit-vul`. With `--fixed-side-check`, a candidate is scored
  as successful only when it both crashes the vulnerable target and passes the
  fixed-side verifier.
- `sage_agent.adapters.MiniGridAdapter`: official Farama MiniGrid smoke adapter.
  It exposes visible grid state and validates that SAGE can generate a reusable
  side-effect-free grid action planner in a third environment that is neither
  ToolSandbox nor CyberGym.
- `sage_agent.adapters.BBHAdapter`: BIG-Bench Hard exact-answer adapter. It
  loads public BBH JSON task files from `external/BIG-Bench-Hard`, exposes only
  prompt text, public task family, and answer format, and keeps target answers
  private inside the adapter scorer.

Run the standalone smoke checks with no model-token spend:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env toolsandbox \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/toolsandbox_smoke_registry

PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env toolsandbox-probe \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/toolsandbox_probe_registry \
  --toolsandbox-scenario search_phone_number_with_name \
  --toolsandbox-scenario update_contact_with_id_and_phone_number

PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env cybergym \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/cybergym_smoke_registry \
  --cybergym-repo external/cybergym \
  --limit 3

PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env minigrid \
  --model gpt-4o-mini \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/minigrid_smoke_registry \
  --limit 9

PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --env bbh \
  --model gpt-4o-mini \
  --baseline llm \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/bbh_smoke_registry \
  --bbh-repo external/BIG-Bench-Hard \
  --limit 40
```

For day-to-day CLI use, `--dataset` is an alias for `--env` and `--samples`
is an alias for `--limit`:

```bash
PYTHONPATH=src:. python scripts/run_sage_agent_smoke.py \
  --dataset minigrid \
  --samples 12 \
  --reset-registry \
  --registry-dir artifacts/sage_standalone/minigrid_cli_registry \
  --no-dashboard-open

make sage_agent SAGE_DATASET=minigrid SAGE_SAMPLES=12 DASHBOARD_OPEN=0
```

Selectable standalone datasets are `toolsandbox`, `toolsandbox-probe`,
`cybergym`, `minigrid`, `bbh`, `tau2-bench`, `tau3-bench`, `terminal-bench`,
`scienceagentbench`, and `science-agent-bench`. The tau, Terminal-Bench, and
ScienceAgentBench entries in the smoke runner are public-metadata probes; they
validate portable SAGE plumbing but are not official benchmark-score runs.

For harness-backed official runs, `scripts/run_sage_official_live.py` uses the
same `SAGEImportAgent` boundary. It currently supports tau2/tau3 and
Terminal-Bench where local official harness dependencies are available.
Baseline controls can use an exact matched baseline cache with
`--baseline-cache use-if-eligible`; SAGE/candidate arms are always fresh.
Tau3 is run through the current `tau2-bench` checkout, which now contains the
tau3 release layer and task fixes; reports and baseline-cache keys are labeled
with `tau3-bench` / `tau3:*` so tau2 and tau3 evidence do not mix.

```bash
set -a; source .secrets/env.sh; set +a
PYTHONPATH=src:external/tau2-bench/src:. python scripts/run_sage_official_live.py \
  --dataset tau2-bench \
  --samples 40 \
  --model gpt-4o-mini \
  --baseline-cache use-if-eligible \
  --retry-policy next_task_only \
  --dashboard-port 62630
```

For ScienceAgentBench, verified task inputs are loaded from Hugging Face, but
official scoring requires the authors' password-protected
`benchmark_verified.zip` artifacts. The setup check is explicit and does not
commit or redistribute those files:

```bash
python scripts/prepare_scienceagentbench_artifacts.py --attempt-download

# If SharePoint requires browser authentication, download benchmark_verified.zip
# manually from the official ScienceAgentBench link, then materialize it:
python scripts/prepare_scienceagentbench_artifacts.py \
  --artifact-zip /path/to/benchmark_verified.zip
```

The official runner records this state in the dashboard:

```bash
PYTHONPATH=src:. python scripts/run_sage_official_live.py \
  --dataset scienceagentbench \
  --samples 4 \
  --model gpt-4o-mini \
  --dashboard-port 62630
```

The current import-agent validation matrix is recorded at
`docs/sage_protocol/sage_import_agent_validation_matrix_20260523.md`. The
latest official tau2 repair rerun scored cached baseline `9/40` and SAGE
`10/40`; Terminal-Bench official40 is a runtime-feasibility blocker until a
valid baseline cache and longer unattended run budget are available.

Each smoke run writes an environment-neutral Task Compare dashboard under
`outputs/sage_agent_standalone/<run_id>/dashboard/task_compare.html`; `index.html`
is kept as the same page for compatibility. The run also writes `summary.json`,
`dashboard_data.json`, `dashboard/task_compare_data.json`, and a copy of the
standalone registry. The dashboard reads only generic SAGE run summary events,
baseline records, task transcripts/artifacts when the adapter exports them, and
registry metadata, so it can render ToolSandbox, CyberGym, or a future adapter
without environment-specific dashboard code. The smoke runner also records a
matched no-generated-helper baseline over the same adapter task stream so the
dashboard can report baseline score, SAGE score, score lift, baseline outcome,
SAGE outcome, and outcome lift when the runner marks that baseline as a valid
comparison. Adapter smoke baselines are lifecycle checks, not benchmark
controls; those are marked as `comparison_valid: false` and described as probe
baselines. The dashboard also records run-mode metadata:
whether the adapter is benchmark-ready, how many tasks the adapter exposes, and
whether real task generation, verifier/server execution, and result ingestion
were used. The current CyberGym adapter is explicitly a synthetic probe, not a
CyberGym benchmark run, until CyberGym data, task generation, PoC server, and
real verifier-backed scoring are connected.

Use `--generator openai` to exercise the live LLM-backed generator through the
same interface. Keep `--model gpt-4o-mini` unless a run protocol explicitly
authorizes a stronger model.

For a real CyberGym submit-path smoke, first download official task files,
generate task directories with CyberGym's own `gen_task`, and run the local
CyberGym server. Then use:

```bash
PYTHONPATH=src:. python scripts/run_cybergym_live_sage.py \
  --reset-registry \
  --registry-dir artifacts/cybergym_live_sage/official10_level1_registry_10of10 \
  --output-root outputs/cybergym_live_sage \
  --run-id official10_level1_live_submit_vul_10of10 \
  --max-candidates 6
```

This live script runs baseline and SAGE through `submit.sh` and the local
`/submit-vul` verifier. It is still a smoke rather than a final CyberGym claim:
it does not run fix-side re-verification and its baseline is a deliberately
simple fixed four-byte PoC.

For a bounded CyberGym validation run that downloads four tasks at a time,
use:

```bash
PYTHONPATH=src:. python scripts/run_cybergym_live_batched_sage.py \
  --limit 20 \
  --batch-size 4 \
  --baseline llm \
  --fixed-side-check \
  --image-pull-workers 4 \
  --reset-registry \
  --registry-dir artifacts/cybergym_live_sage/general_gap_v2_registry \
  --output-root outputs/cybergym_live_sage \
  --run-id general_gap_v2_20 \
  --max-candidates 32
```

This starts SAGE from an empty generated-helper registry, preserves the registry
across batches, uses only visible task assets and live submit feedback, and
clears batch task directories by default. Docker images are retained and reused
by default because they are environment setup artifacts, not answer labels or
reference PoCs. The runner skips image pulls when the exact requested image is
already present and can pull each batch's vulnerable/fixed images in parallel
with `--image-pull-workers`.
The current batched runner starts with no generated helpers and can birth
several generic candidate-planning families from the same failed task:
visible-text planning, visible-artifact literal extraction, execution-feedback
mutation, and structured-format input planning. It does not encode CyberGym
task IDs, hidden labels, reference PoCs, expected answers, or benchmark-specific
facts into generated helpers. Use `--clear-images` only when disk pressure
matters more than runtime; it forces the next run to pay the Docker image setup
cost again.

The current CyberGym-driven generalization loop also supports two higher-level
candidate families that are still environment-neutral:

- **Adaptive candidate portfolio planning** combines visible literals, source
  boundaries, structured-format cues, previous failed attempts, and generic
  numeric/parser/binary seeds into one bounded candidate list.
- **Format-edge candidate planning** is born only after SAGE already has
  multiple generic candidate planners and sees a recurring visible format cue
  such as XML, regex, numeric parsing, or packet/protocol input. This gating
  prevents premature format-specific helpers from being born from vague text.

The controller also limits helper churn by stopping further gap processing for
a task once a newly born or refined helper succeeds on the same task, waiting
for enough natural-use evidence before refining an existing helper, and capping
new helper births per task. These are general lifecycle policies intended to
make SAGE more portable to future benchmarks with expensive task execution.

When `--fixed-side-check` is enabled, the runner also pulls the matching fixed
image and requires fixed-side preservation before counting a CyberGym success.
The LLM baseline cache key includes the fixed-side setting, so older
vulnerable-only baseline cache entries are not reused as fixed-side evidence.
If the matched baseline starts at zero and SAGE improves, the dashboard reports
an approximate relative lift using a documented `0.100` denominator floor and
shows the true absolute lift in the card note. For example, `0.000 -> 0.500`
renders as approximately `+500.0%`, with the note making clear that the true
baseline was zero.

For real ToolSandbox verification, use `scripts/run_sage_protocol.py` with a
fixed manifest and `OPENAI_API_KEY` available in the process environment. For
generation-enabled mechanism or online-build runs, the default `--sage-policy
auto` activates the self-evolving Praxis policy. For frozen validation arms,
generation remains off and `auto` resolves to no policy preset. Do not interpret
`toolsandbox-probe` smoke baselines as ToolSandbox benchmark baselines.

Example ToolSandbox self-evolving verification command:

```bash
PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode mechanism_40 \
  --manifest artifacts/sage_standalone/toolsandbox_verify20_manifest.json \
  --generation on \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --disable-openai-response-cache \
  --cache-mode off \
  --control-cache strict \
  --routing-evidence-mode disabled \
  --allow-low-quality-cohort \
  --output-root outputs/sage_agent_standalone/toolsandbox_verify20_self_evolving_policy \
  --artifact-root artifacts/sage_standalone/toolsandbox_verify20_self_evolving_policy_artifacts
```

Architecture notes are in
`docs/sage_protocol/standalone/sage_standalone_architecture.md`.
Validation notes are in
`docs/sage_protocol/standalone/sage_standalone_validation_report.md`.

### Using SAGE on a New Benchmark Dataset

To run SAGE on a new environment, implement the `EnvironmentAdapter` protocol
from `src/sage_agent/interfaces.py`. Keep the environment-specific work inside
the adapter and keep SAGE-facing data clean:

1. `profile()` describes public capabilities: base tools, action tools,
   observable fields, helper families, and safety rules.
2. `prepare()` downloads or starts local environment resources.
3. `tasks(limit=...)` returns a sealed task stream. Do not select tasks based
   on labels, cache hits, or prior SAGE performance.
4. `run_task(task, helpers)` executes the task with a bounded helper bundle and
   returns normalized score, outcome, transcript, helper uses, and visible
   artifacts.
5. `observe_gap(task, result, helpers)` converts failure or friction into a
   reusable capability gap. It should describe the missing deterministic step,
   not the hidden answer.
6. `validation_cases_for_gap(gap)` provides synthetic or visible-data validation
   cases, including abstain/minefield cases.
7. `route_helpers(task, registry)` selects a small relevant helper bundle from
   the accepted registry. The actor or environment still decides whether to
   use a visible helper naturally.

Adapters may privately score tasks, submit files, step simulators, or call
benchmark servers. Generated helpers must remain side-effect-free unless a
future run protocol explicitly permits a different class. Do not expose
`expected_answer`, `ground_truth`, `oracle`, `solution`, `answer_key`, prior
SAGE traces, reference PoCs, or hidden labels through task metadata, artifacts,
gap signals, generation directives, helper code, or registry metadata. The
standalone integrity policy fails fast if those leak-prone fields appear.

Minimal runner pattern:

```python
from pathlib import Path

from sage_agent import SAGEAgent, SAGEConfig, TemplateHelperGenerator
from my_env_adapter import MyBenchmarkAdapter

agent = SAGEAgent(
    adapter=MyBenchmarkAdapter(data_root=Path("external/my-benchmark")),
    generator=TemplateHelperGenerator(),  # or OpenAIHelperGenerator()
    config=SAGEConfig(
        model="gpt-4o-mini",
        registry_dir=Path("artifacts/my_benchmark/sage_registry"),
    ),
)
summary = agent.run(limit=20)
```

For large or disk-heavy benchmarks, use the CyberGym pattern: download a small
batch, generate task directories, run baseline and SAGE, preserve only the SAGE
registry and summaries, clear batch resources, and continue with the next batch.
The registry is the evolving memory; the task data does not need to remain
loaded.

Recent standalone generalization checks:

- ToolSandbox matched 40-task self-evolving Praxis verification:
  `outputs/sage_agent_standalone/toolsandbox_verify40_self_evolving_policy_20260521/mechanism_40_20260521_175250`
  used `40 cached / 0 fresh` controls and fresh SAGE execution. Score improved
  `0.647929 -> 0.874999` (`+0.227070`), outcome improved
  `0.473734 -> 0.907297` (`+0.433562`), exact successes moved `3 -> 24`,
  runtime exceptions were `0`, and the generated registry contained `14`
  accepted helpers.
- CyberGym live batched 40-task smoke:
  `outputs/cybergym_live_sage/final_agent_cybergym_live40_20260521`
  used ten four-task batches, fully cached controls (`40 cached / 0 fresh`),
  and fresh SAGE execution. Cached LLM-visible-artifact baseline success was
  `1/40`; SAGE success was `4/40`; tools born/accepted/reused were
  `12 / 12 / 237`; repair attempts/refined tools were `9 / 9`; integrity issues
  were `0`. This is live `/submit-vul` portability evidence, not final CyberGym
  benchmark evidence because fix-side verification is not yet run.
- MiniGrid official 40-task check:
  `outputs/sage_agent_standalone/minigrid_live40_20260521`
  improved the LLM baseline from `21/40` to `40/40` by birthing and reusing
  `plan_grid_shortest_path_actions`; integrity issues were `0`.
- BIG-Bench Hard 40-task check:
  `outputs/sage_agent_standalone/bbh_live40_20260521`
  improved the LLM exact-answer baseline from `16/40` to `40/40`. The task mix
  was intentionally broad within the adapter: `10` examples each from
  `boolean_expressions`, `multistep_arithmetic_two`, `dyck_languages`, and
  `word_sorting`. SAGE produced one accepted helper because a single reusable
  symbolic exact-answer helper generalized across those public task families;
  target answers stayed private inside the adapter scorer.

Machine-readable four-environment summary:
`artifacts/sage_agent_standalone/final_four_env_live40_summary_20260521.json`.

## Current Evidence Snapshot

The protected broad validated portfolio is frozen best3:

- `relative_day_time_to_timestamp`
- `resolve_search_window_or_bounds`
- `select_record_by_timestamp_extreme`

Best3 has positive broad validation at 100, 250, 500, and 1,032 scenarios, with the formal250 run showing a `+20.52%` relative outcome/task-completion lift. Outcome/task completion is the primary claim metric; canonical/reference similarity is secondary.

The V2.6 expanded contact-scalar portfolio is separate secondary evidence. It is current-code non-harmful and modestly outcome-positive on original250 and non-external500, and it shows strong matched gap-enriched closure, but it is not framed as an unconditional broad replacement for best3.

Pre-final hardening artifacts:

- Final-run preflight: `scripts/preflight_final_run.py`
- Preflight config: `docs/sage_protocol/final_run_preflight_config.json`
- Versioned methodology heuristics: `docs/sage_protocol/protocol_heuristics_v1.json`
- Statistical analysis script: `scripts/write_final_statistical_analysis.py`
- Statistical report: `docs/sage_protocol/final_statistical_analysis_report.md`
- Chapter 3 methodology prep: `docs/sage_protocol/chapter3_methodology_prep.md`

Before any future frozen final run, use generation OFF, control cache `use-if-eligible`, and explicit routing evidence mode (`disabled` or `pinned`). Diagnostic force-call environment variables are blocked for frozen final runs unless explicit diagnostic mode is selected.

## Praxis Combined Treatment Review

The Praxis high-lift candidate is being reviewed as an explicit combined SAGE
treatment: a frozen helper registry plus a feature-flagged actor/checker bridge
policy. This should not be described as registry-only unless a separate
bridge-disabled ablation reproduces it.

- Combined registry:
  `artifacts/praxis_safety_repair/registries/praxis_bridgepack_combined_bridge_policy_v1/registry_manifest.json`
- Registry SHA-256:
  `7867cde8c8709f31efb02006e8c0743bbf890f2ede1519de99155e4631614349`
- Bridge flag:
  `SAGE_PRAXIS_BRIDGE_POLICY=combined`
- Methodology note:
  `docs/sage_protocol/praxis_bridge_policy_methodology.md`
- Latest combined-treatment formal500 review:
  canonical/reference `0.670 -> 0.757` (`+13.0%` relative lift), outcome/task completion `0.595 -> 0.840` (`+41.2%` relative lift), runtime exceptions `0`, helper side-effect incidents `0`.
- Latest formal500 report:
  `docs/sage_protocol/praxis_combined_bridge_policy_formal500_report.md`

Example clean review run:

```bash
export PYTHONPATH=src:.
export SAGE_PRAXIS_BRIDGE_POLICY=combined
export TOOLSANDBOX_RAPID_CACHE_MODE=read_only
export TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json

python scripts/run_sage_protocol.py \
  --mode validate_100 \
  --manifest artifacts/praxis_combined_bridge_policy/manifests/formal500_order_first100_clean.json \
  --registry-dir artifacts/praxis_safety_repair/registries/praxis_bridgepack_combined_bridge_policy_v1 \
  --generation off \
  --disable-openai-response-cache \
  --cache-mode off \
  --parallel-arms \
  --control-cache use-if-eligible \
  --routing-evidence-mode disabled \
  --output-root outputs/praxis_combined_bridge_policy/formal500_order_first100_clean \
  --artifact-root artifacts/praxis_combined_bridge_policy/run_artifacts/formal500_order_first100_clean
```

Controls may use eligible task-level baseline cache; candidate/SAGE arms must
remain fresh. Task Compare is the default dashboard for new runs and includes
canonical lift, outcome lift, per-task comparisons, and generated-tool
contribution details.

To browse prior run dashboards from one port, use the dashboard picker:

```bash
python3 scripts/serve_dashboard_picker.py --host 127.0.0.1 --port 62624 --root .
```

Then open `http://127.0.0.1:62624/`. The picker lists all
`outputs/**/dashboard/task_compare.html` dashboards, newest first, and falls
back to Task Focus or the standard dashboard for older runs that do not have
Task Compare.

The combined result is promising but remains a review treatment, not a protected
final-claim update. A protected claim should run a dedicated matched ablation
under the same committed runtime for best3, V2.6, Praxis registry-only, and
Praxis combined bridge-policy arms.

## Self-Evolving SAGE Current Approach

The current SAGE development approach now includes an explicit live
self-evolving controller slice:

1. observe a machine-readable gap packet from a completed run,
2. rank unsupported or regressing task buckets,
3. select the next high-opportunity bucket without inspecting hidden labels,
4. start from an empty generated-tool registry,
5. keep generation on during the candidate run,
6. generate and validate tools from online inadequacy observations,
7. run a capped natural-adoption gate with cached controls and fresh SAGE arms,
8. reflect with a `scale`, `refine`, `recombine`, `park`, or `block` decision.

Low-cost discovery campaigns can be forced to `gpt-4o-mini` for every model role
and capped at 60 tasks:

```bash
PYTHONPATH=src:. python scripts/prepare_self_evolving_sage_mini60.py \
  --output-root artifacts/self_evolving_sage/current_mini60_live_generation_v2 \
  --max-samples 60 \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --split-name mechanism_60 \
  --tool-strategy empty_live_generation
```

Then run the prepared manifest with cached controls and fresh candidate/SAGE
tasks. Generation must stay on for this live self-evolving proof. Prefer the
first-class policy preset so the run records the complete self-evolving Praxis
runtime stack in `protocol_manifest.json`:

```bash
PYTHONPATH=src:. python scripts/run_sage_protocol.py \
  --mode mechanism_60 \
  --manifest artifacts/self_evolving_sage/current_mini60_live_generation_v2/self_evolving_mini60_manifest.json \
  --registry-dir artifacts/self_evolving_sage/current_mini60_live_generation_v2/registry \
  --sage-policy self-evolving-praxis \
  --agent gpt-4o-mini \
  --user gpt-4o-mini \
  --generation-model gpt-4o-mini \
  --generation on \
  --disable-openai-response-cache \
  --cache-mode off \
  --parallel-arms \
  --control-cache use-if-eligible \
  --routing-evidence-mode disabled \
  --allow-low-quality-cohort \
  --output-root outputs/self_evolving_sage/live_generation_v_next_diag24 \
  --artifact-root artifacts/self_evolving_sage/campaign_artifacts_live_generation_v_next_diag24
```

`--sage-policy self-evolving-praxis` expands to the high-lift audited defaults:
just-in-time proactive helper birth, same-task fair chance for newly accepted
helpers, safe-abstain birth, the combined Praxis actor bridge policy, transient
scenario retries, V2 contract synthesis/repair/dependency/medium-grain
generation features, and task-level control-cache matching. Explicit
environment variables are preserved and recorded if a run intentionally
overrides any default.

By default, each protocol run opens the new Task Compare dashboard
(`dashboard/task_compare.html`) in the external browser. The runner also writes
`dashboard_urls.json` with `default_dashboard: "task_compare"`. Use
`--no-dashboard-open` only when running unattended.

Latest scale evidence:

- report:
  `docs/sage_protocol/self_evolving_sage_mini60_report.md`
- clean committed-tree broad500 reproduction summary:
  `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v71_clean_repro_summary.json`
- clean committed-tree broad500 reproduction run:
  `outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356`
- clean committed-tree broad500 reproduction dashboard:
  `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v71_clean_repro/online_build_500_20260514_204356/dashboard/task_compare.html`
- clean committed-tree broad500 reproduction result:
  score `0.656799 -> 0.854188`, lift `+30.05%`; outcome `0.494746 -> 0.880845`, lift `+78.04%`; controls `500 cached / 0 fresh`; generation on from an empty generated registry; accepted generated helpers `16`; naturally called generated-tool scenarios `297`; generated-tool failures `0`; runtime exceptions `0`
- clean-run caveat:
  one helper-contract side-effect preservation failure was reported on a read-only reminder-search task. No state mutation occurred, but protected final-claim readiness requires repairing or adjudicating that preservation near miss.
- broad500 JIT same-task birth summary:
  `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v70_jit_birth_retry_repair_summary.json`
- broad500 JIT same-task birth run:
  `outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839`
- broad500 JIT same-task birth dashboard:
  `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v70_jit_birth_retry_repair/online_build_500_20260513_174839/dashboard/task_compare.html`
- broad500 JIT same-task birth result:
  score `0.656799 -> 0.827506`, lift `+25.99%`; outcome `0.494746 -> 0.872782`, lift `+76.41%`; controls `500 cached / 0 fresh`; generation on from an empty generated registry; accepted generated helpers `16`; naturally called generated-tool scenarios `295`; generated-tool failures `0`; runtime/helper incidents `0 / 0`
- broad250 summary:
  `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v37_broad250_system_lifecycle_keyfixed_summary.json`
- broad250 run:
  `outputs/self_evolving_sage/formal500_live_generation_v37_broad250_system_lifecycle_keyfixed/online_build_250_20260512_220851`
- broad250 dashboard:
  `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v37_broad250_system_lifecycle_keyfixed/online_build_250_20260512_220851/dashboard/task_compare.html`
- broad250 result:
  score `0.669502 -> 0.779703`, lift `+16.46%`; outcome `0.509662 -> 0.685953`, lift `+34.59%`; controls `250 cached / 0 fresh`; accepted generated helpers `15`; runtime/helper incidents `0 / 0`
- broad500 summary:
  `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v38_broad500_system_lifecycle_keyfixed_summary.json`
- broad500 run:
  `outputs/self_evolving_sage/formal500_live_generation_v38_broad500_system_lifecycle_keyfixed/online_build_500_20260513_005654`
- broad500 dashboard:
  `http://127.0.0.1:62624/outputs/self_evolving_sage/formal500_live_generation_v38_broad500_system_lifecycle_keyfixed/online_build_500_20260513_005654/dashboard/task_compare.html`
- broad500 result:
  score `0.657730 -> 0.738692`, lift `+12.31%`; outcome `0.495416 -> 0.700468`, lift `+41.39%`; controls `500 cached / 0 fresh`; accepted generated helpers `16`; naturally called generated helpers `15`; runtime/helper incidents `0 / 0`

Broad500 resumed after an OpenAI transport hang, so it is reported with a
resume caveat. The completed paired metrics are valid, but the lifecycle
reflection state did not fully hydrate at the resume boundary. The runtime now
hydrates cumulative lifecycle state from copied `self_evolution_task_feedback.jsonl`
on resumed runs, and long OpenAI calls use `SAGE_OPENAI_REQUEST_TIMEOUT_SECONDS`
to avoid unbounded socket waits.

Earlier live-generation mechanism proof:

- report:
  `docs/sage_protocol/self_evolving_sage_mini60_report.md`
- summary:
  `artifacts/self_evolving_sage/summary/self_evolving_live_generation_v21_60_summary.json`
- positive run:
  `outputs/self_evolving_sage/live_generation_v21_60_safe_remove_bridge/mechanism_60_20260512_073507`
- dashboard:
  `http://127.0.0.1:62624/outputs/self_evolving_sage/live_generation_v21_60_safe_remove_bridge/mechanism_60_20260512_073507/dashboard/task_compare.html`
- score delta:
  `+0.099638`
- score lift:
  `+13.19%`
- outcome delta:
  `+0.143150`
- live-born retained tools:
  `plan_contact_lookup_query`, `plan_contact_relationship_batch_update`,
  `plan_contact_update_from_id`, `prepare_side_effect_args_from_selected_record`,
  `select_action_target_by_recency`, `select_record_by_timestamp_extreme`
- natural call evidence:
  `18` generated-tool call scenarios, `0` generated-tool failures;
  `plan_contact_lookup_query` called `8` times, called-subset outcome delta
  `+0.473296`; `plan_contact_relationship_batch_update` called `8` times,
  called-subset outcome delta `+0.436380`
- runtime exceptions and helper side-effect incidents:
  `0 / 0`

This is experimental implementation evidence, not protected final-claim
evidence. It demonstrates empty-registry, generation-on tool birth under strict
low-cost model and sample constraints, plus a documented combined bridge-policy
safe-abstention repair for remove-by-phone requests when contact search is not
available. The earlier
`mini60_praxis_pack_v2` run remains useful as a recipe-pack transfer
diagnostic, but it used pre-existing Praxis recipe tools and generation off, so
it is not proof of autonomous live self-evolution.

When external location/weather/search tasks are in scope, use the ToolSandbox
RapidAPI cache in `read_only` mode to avoid quota spend during review gates.
The local cache file remains under ignored `.secrets/`; document its SHA-256,
source run, and hit/miss policy in the run report. A read-only cache miss should
fail visibly rather than falling through to live RapidAPI calls. This cache is
external-service data, not SAGE task-output evidence; SAGE/candidate task cache
must still remain off for evidence arms.

---

# Upstream ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities

This software project accompanies the research paper, [ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities](https://arxiv.org/abs/2408.04682).

Recent large language models (LLMs) advancements sparked a growing research interest in tool assisted LLMs solving real-world challenges, which calls for comprehensive evaluation of tool-use capabilities. While previous works focused on either evaluating over stateless web services (RESTful API), based on a single turn user prompt, or an off-policy dialog trajectory, _ToolSandbox_ includes stateful tool execution, implicit state dependencies between tools, a built-in user simulator supporting on-policy conversational evaluation and a dynamic evaluation strategy for intermediate and final milestones over an arbitrary trajectory. We show that open source and proprietary models have a significant performance gap, and complex tasks like State Dependency, Canonicalization and Insufficient Information defined in _ToolSandbox_ are challenging even the most capable SOTA LLMs, providing brand-new insights into tool-use LLM capabilities.

## Getting started
### Installation
1. Install your favorite Python virtual environment manager. We have used the arm64 (Apple Silicon) version of Miniforge3 with Python 3.9 by downloading and running the following script: https://github.com/conda-forge/miniforge/releases/download/4.12.0-2/Miniforge3-MacOSX-arm64.sh .

2. Create a virtual environment:
```bash
conda create -n ToolSandbox python=3.9
conda activate ToolSandbox
```

3. Install the dependencies with:
```bash
pip install '.[dev]'
```

### Execution
#### Required configuration for the different user/agent roles:

The following table shows the required environment variables to set depending on the user type:

|User Type  | CLI Option         | OPENAI_API_KEY |
| --------- | ------------------ | :------------: |
| Simulator | GPT_3_5_0125       | ✅             |
| Simulator | GPT_4_0125         | ✅             |
| Simulator | GPT_4_o_2024_05_13 | ✅             |
| Human     | Cli                |                |


The following table shows the required environment variables to set depending on the agent type:

| Agent Type            | ANTHROPIC_API_KEY | HF_TOKEN | OPENAI_API_KEY | OPENAI_BASE_URL | GOOGLE_CLOUD_PROJECT or CLOUD_ML_PROJECT_ID | GOOGLE_CLOUD_REGION or CLOUD_ML_REGION |
| --------------------- | :---------------: | :------: | :------------: | :-------------: | :-----------------------------------------: | :------------------------------------: |
| Claude_3_Haiku        | ✅                |          |                |                 |                                             |                                        |
| Claude_3_Opus         | ✅                |          |                |                 |                                             |                                        |
| Claude_3_Sonnet       | ✅                |          |                |                 |                                             |                                        |
| Cli                   |                   |          |                |                 |                                             |                                        |
| Cohere_Command_R      |                   |          |                | ✅              |                                             |                                        |
| Cohere_Command_R_Plus |                   |          |                | ✅              |                                             |                                        |
| GPT_3_5_0125          |                   |          | ✅             |                 |                                             |                                        |
| GPT_4_0125            |                   |          | ✅             |                 |                                             |                                        |
| GPT_4_o_2024_05_13    |                   |          | ✅             |                 |                                             |                                        |
| Gemini_1_0            |                   |          |                |                 | ✅                                          | ✅                                     |
| Gemini_1_5            |                   |          |                |                 | ✅                                          | ✅                                     |
| Gemini_1_5_Flash      |                   |          |                |                 | ✅                                          | ✅                                     |
| Gorilla               |                   |          |                | ✅              |                                             |                                        |
| Hermes                |                   |          |                | ✅              |                                             |                                        |
| Mistral               |                   |          |                | ✅              |                                             |                                        |

The search tools in the ToolSandbox use [RapidAPI](https://rapidapi.com/hub) so in order to run those scenarios you need to have an API key and expose it in an environment variable called `RAPID_API_KEY`. Using models from the Gemini family requires setting up google authentication, e.g. by using [application default credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc).

#### Example command for a single scenario
It is recommended to just set the environment variables for the command that is running as opposed to exporting them e.g. in your `~/.bashrc` file. This makes it less likely to accidentally use stale environment variables. Here is an example command to run a ToolSandbox scenario using GPT-4o as the user simulator and Claude 3 Haiku as the agent:
```
env ANTHROPIC_API_KEY=<YOUR_ANTHROPIC_API_KEY> OPENAI_API_KEY=<YOUR_OPENAI_API_KEY> tool_sandbox --user GPT_4_o_2024_05_13 --agent Claude_3_Haiku --scenario wifi_off
```

Artifacts will be stored under the `data` folder within the repository's root directory. You can for example take a look at `data/agent_claude-3-haiku-20240307_user_gpt-4o-2024-05-13_07_03_2024_00_17_44/result_summary.json` to view the evaluation results. The full dialog of each scenario is stored within a `trajectories` subdirectory, e.g. `data/agent_gpt-4o-2024-05-13_user_gpt-4o-2024-05-13_07_03_2024_00_17_44/trajectories/wifi_off/conversation.json`.

#### Hosting open source models
Open source models can be hosted using [vLLM's OpenAI Compatible Server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html). At the time of writing this the latest version was [0.5.0.post1](https://github.com/vllm-project/vllm/releases/tag/v0.5.0.post1). Here is an example to serve the `gorilla-llm/gorilla-openfunctions-v2` model:
```
pip install vllm
python3 -m vllm.entrypoints.openai.api_server --model gorilla-llm/gorilla-openfunctions-v2
```
Note that when serving a model for the first time it may be necessary to set the Hugging Face token using the `HF_TOKEN` environment variable:
```
env HF_TOKEN=<YOUR_HF_TOKEN> python3 -m vllm.entrypoints.openai.api_server --model gorilla-llm/gorilla-openfunctions-v2
```
Depending on your GPU you may have to explicitly set the `dtype` with e.g. `--dtype=half`. By default, the above command will host an OpenAI compatible server at http://0.0.0.0:8000. The following lines of Python code can be used to quickly test that the server can be reached:
```python
import openai
openai_client = openai.OpenAI(api_key="EMPTY", base_url="http://0.0.0.0:8000/v1")
print(openai_client.models.list())
```
On success, this should print the models hosted by the server. Note that these instructions assume that the client and server run on the same compute instance. If the server is running on a different compute instance, the compute instance running the client can use SSH port forwarding to access the server. This example runs a single scenario using the `Gorilla` agent:
```
env OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>  OPENAI_BASE_URL="http://0.0.0.0:8000/v1" tool_sandbox --agent Gorilla -s wifi_off
```

#### Example command for running all scenarios
By default, if `--scenario` is not provided all scenarios will be executed. Here is an example command using GPT-4o as both the user simulator and agent:
```
env OPENAI_API_KEY=<YOUR_OPENAI_API_KEY> RAPID_API_KEY=<YOUR_RAPID_API_KEY> tool_sandbox --user GPT_4_o_2024_05_13 --agent GPT_4_o_2024_05_13
```
Notebooks for introspecting and comparing the results can be found [here](tool_sandbox%2Fnotebooks).

#### Development setup
1. Setup pre-commit hooks. Includes multiple linters
```bash
pre-commit install --hook-type pre-commit
```

2. If some hooks are too slow and you would wish to skip them, you can do so with `SKIP` env variable. For example
```bash
SKIP="mypy" git commit -m "temporary commit that might not pass mypy"
```

## Documentation

The following sections introduce the core design and concepts.

### Execution context
The execution context stores the complete state of the tool sandbox. More specifically, the tools, dialog history between the different roles and the world state. It also stores a snapshot of the state at every turn, which is used for introspection and evaluation. The world state consists of:
- a settings database (e.g. cellular service status, WiFi status)
- a contact book
- a messaging database (storing text messages that have been "sent")
- a reminder database (storing reminders that have been created)

### Tools
The implemented tools are a set of highly composable, explicitly or implicitly dependent Python functions, creating complex reasoning challenges. Tools can manipulate the world state through the execution context. Here is an example tool:
```
@register_as_tool(visible_to=(RoleType.AGENT,))
@typechecked
def remove_contact(person_id: str) -> None:
    """Remove an existing contact person to contact database.

    Args:
        person_id:      String format unique identifier of the person to be deleted

    Returns:

    Raises:
        NoDataError:    If the provided person_id was not found
    """
    validate_type(person_id, "person_id", str)

    current_context = get_current_context()
    current_context.remove_from_database(
        namespace=DatabaseNamespace.CONTACT, predicate=pl.col("person_id") == person_id
    )
```
A Python function is registered as a tool with the `register_as_tool` decorator. Note that when defining a scenario the developer can decide which tools should be visible to the agent. You can find the available tools [here](tool_sandbox%2Ftools).

### Roles
The roles interacting in the tool sandbox are the system, user, agent and execution environment. This is more generic than the usual chat and agent roles commonly used in proprietary APIs. The interaction between the roles is based on a message passing system. Each message specifies the sender, recipient and to which roles it is visible to.

#### User
The user represents a human interacting with an agent hoping to complete a task. The user role decides when the task is complete by using the `end_conversation` tool, which is the only tool available to the user. The user can be a real human or it can be simulated by an agent.

#### Agent
The agent initially receives a message from the user in natural language specifying the task to be completed. The agent can then decide to respond to the user (e.g. asking for clarification) or send a tool use request to the execution environment. These agents have been implemented:
- Claude Opus, Sonnet, Haiku ([Anthropic](https://www.anthropic.com/claude))
- Command R and Command R Plus ([Cohere](https://cohere.com/command))
- Gemini ([Google](https://deepmind.google/technologies/gemini/))
- Gorilla ([UC Berkeley](https://gorilla.cs.berkeley.edu))
- GPT ([OpenAI](https://platform.openai.com/docs/models))
- Human via CLI

The agents are defined [here](tool_sandbox%2Froles).

#### Execution environment
The execution environment executes tool calls requested by the agent. The implementation is based on Python's [code.InteractiveConsole](https://docs.python.org/3.9/library/code.html#code.InteractiveConsole) module. The tool result is captured via `stdout` and potential exceptions are captured via `stderr`. This is similar to executing code in a Jupyter notebook. If an exception occurs it is communicated back to the agent such that it can refine its tool call and try again.
Note that the code is executed directly on the host machine and not in e.g. a sandbox like a docker container. At the moment this is acceptable since
- we do not allow the agent to run arbitrary Python code, but it can only select from the tools we have implemented
- we have full control over which tools exist and how they are implemented

However, with the current implementation a developer could get quite sad if we added a new `rm_dir` tool and the agent requests a tool call like `rm_dir("/")`.

### Scenario
Scenarios are defined in Python as extensions to a base setup. One can think of the base setup as the initial device state.
```
ScenarioExtension(
    name="cellular_off",
    base_scenario=base_scenarios["base"],
    messages=[
        {
            "sender": RoleType.SYSTEM,
            "recipient": RoleType.USER,
            "content": USER_INSTRUCTION + "Turn off cellular service",
        },
        {
            "sender": RoleType.USER,
            "recipient": RoleType.AGENT,
            "content": "Turn off cellular",
        },
    ],
    tool_allow_list=["set_cellular_service_status"],
    milestones=[
        Milestone(
            snapshot_constraints=[
                SnapshotConstraint(
                    database_namespace=DatabaseNamespace.SETTING,
                    snapshot_constraint=snapshot_similarity,
                    target_dataframe=pl.DataFrame(
                        {
                            "cellular": False,
                        }
                    ),
                )
            ]
        ),
        Milestone(
            snapshot_constraints=[
                SnapshotConstraint(
                    database_namespace=DatabaseNamespace.SANDBOX,
                    snapshot_constraint=snapshot_similarity,
                    target_dataframe=pl.DataFrame(
                        {
                            "sender": RoleType.AGENT,
                            "recipient": RoleType.USER,
                            "content": "Cellular service is turned off",
                        }
                    ),
                )
            ]
        ),
    ],
)
```
#### Tool augmentations
Note that several tool augmentations are supported:
- adding tools not needed to complete the task (distraction tools)
- scrambling the tool name (i.e. renaming the tool to something less informative `set_cellular_service_status` to `settings_0` forcing the agent to use the docstring when deciding which tool to use)
- removing the argument descriptions of the tools
- renaming the arguments in the docstring (e.g. `arg_0` instead of `phone_number`)
- removing the argument type hints forcing the agent to guess the data type or figuring it out through trial and error

#### Scenario categories
The scenarios are categorized in order to gain insight into what agents can handle well. Note that a scenario can belong to multiple categories at the same time. The categories are:
- Single/multiple tool call. This is based on how many tool uses are needed to achieve the task.
- Single/multiple user turn. If a user provides all necessary information in the initial message to the agent then the scenario is considered a single turn scenario.
- State dependency. These are categories where successful tool execution depends on the world state (e.g. enabling some setting using another tool before being able to use the tool to perform the user's task). In these cases there is an implicit dependency between tools / a tool and the world state, which the agent needs to discover through trial and error.
- Canonicalization. This category is for scenarios where natural language information needs to be transformed into its corresponding canonical form. In some cases the agent can directly do this (e.g. converting `1k` to `1000`), but in other cases it requires a tool (e.g. converting `this Friday` to `14th of June 2024`).
- Insufficient information. In these scenarios necessary tools or information are held back on purpose such that the agent is unable to perform the user's task. The motivation is to see if the agent can identify that it is unable to complete the task or if it instead hallucinates tools or tool arguments.

### Evaluation

Many different trajectories could lead to the same outcome. There could be different tools that can complete the task,
the agent could fail to complete and ask the user for additional input, or figure things out with the execution environment
through trial and error. This makes evaluation extra difficult for an interactive environment. However, between all these
possibilities, there's often a few **_critical milestones_** we need to hit in order to complete the task.

For example, suppose
1. The user's cellular service is currently off
2. The user wants to send a message to Fredrik Thordendal saying: 'How's the new album coming along.'.

Given the tools available to us, we know a few things must happen in the following order to achieve the goal:

0. **_First_**, at some point, the cellular status in SETTINGS database should be `True` **_exactly_**
1. **_Parallel to 0_**, agent must make a tool call to with `search_contacts` tool and `{"name": "Fredrik Thordendal"}` argument **_exactly_**
2. **_After 0 & 1_**, the MESSAGING database should contain a message
   1. from the phone number +12453344098 **_exactly_**
   2. saying **_something close to_** How's the new album coming along.
3. **_After 2_**, agent should confirm to the user that the message has been sent, saying **_something close to_** `"Your message to Fredrik Thordendal has been sent saying: How's the new album coming along"`

We don't know exactly when these milestones shall happen, but we know they must happen in this order at some point
in the trajectory. This is the general design principle of our evaluation. To make this a little more formal


1. Evaluation criteria is defined with a Milestone DAG. Directional edges define the sequential order of each milestone.
   In the example above, the edges would be `[(0, 2), (1, 2), (2, 3)]`
2. Each milestone contains multiple similarity measures, calculating the [0, 1] similarity between this milestone
   and each step in the trajectory. Similarity measures are allowed to depend on other milestones. These similarities include:
   1. snapshot_similarity: How close is a database to a target database
   2. addition_similarity: How close is a database to a target database, if the target database was derived from adding
      k target rows into a reference database
   3. removal_similarity: How close is a database to a target database, if the target database was derived from removing
      k target rows from a reference database
   4. update_similarity: How close is a database to a target database, if the target database was derived from updating
      k target rows in a reference database
   5. tool_trace_dependant_similarity: How close is a database to a target database, if the target database includes
      values extracted from the tool_trace of a reference database
   6. guardrail_similarity: The database should be identical to a reference database, otherwise this similarity is 0
3. Each milestone similarity further breaks down into column-wise similarity, which can be **_exact_match_**, **_rouge_l_**
   etc. Allowing for more customization in matching logic
4. Milestone similarity is derived by calculating the geometric mean of all its similarity measures.
   1. Geo mean ensures if 1 exact matching similarity returns 0, the whole milestone similarity is 0.
5. An optimal match between milestones and trajectory is found by maximizing the arithmetic mean of all milestone similarities
   under the constraint that matched milestone order should be one possible topological sort of the Milestone DAG.

The milestones in the example above can be described as follows

```python
milestones = [
    Milestone(
        snapshot_constraints=[
            SnapshotConstraint(
                database_namespace=DatabaseNamespace.SETTING,
                snapshot_constraint=snapshot_similarity,
                target_dataframe=pl.DataFrame(
                    {
                        "cellular": True,
                    }
                ),
            )
        ]
    ),
    Milestone(
        snapshot_constraints=[
            SnapshotConstraint(
                database_namespace=DatabaseNamespace.SANDBOX,
                snapshot_constraint=snapshot_similarity,
                target_dataframe=pl.DataFrame(
                    {
                        "sender": RoleType.AGENT,
                        "recipient": RoleType.EXECUTION_ENVIRONMENT,
                        "tool_trace": json.dumps(
                            {
                                "tool_name": "search_contacts",
                                "arguments": {"name": "Fredrik Thordendal"},
                            },
                            ensure_ascii=False,
                        ),
                    }
                ),
            )
        ]
    ),
    Milestone(
        snapshot_constraints=[
            SnapshotConstraint(
                database_namespace=DatabaseNamespace.MESSAGING,
                snapshot_constraint=addition_similarity,
                target_dataframe=pl.DataFrame(
                    {
                        "recipient_phone_number": "+12453344098",
                        "content": "How's the new album coming along",
                    },
                ),
                reference_milestone_node_index=0,
            )
        ]
    ),
    Milestone(
        snapshot_constraints=[
            SnapshotConstraint(
                database_namespace=DatabaseNamespace.SANDBOX,
                snapshot_constraint=snapshot_similarity,
                target_dataframe=pl.DataFrame(
                    {
                        "sender": RoleType.AGENT,
                        "recipient": RoleType.USER,
                        "content": "Your message to Fredrik Thordendal has been sent saying: "
                                   "How's the new album coming along",
                    }
                ),
            )
        ]
    ),
]
# search_contacts and set_cellular_service_status can happen in any order
edge_list = [(0, 2), (1, 2), (2, 3)]
```
Here's an example trajectory collected from `gpt-3.5-turbo-0125`, as well as the evaluation results
```
shape: (15, 5)
+-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------+
| sandbox_message_index | sender                | recipient             | content                                  | tool_trace                              |
| ---                   | ---                   | ---                   | ---                                      | ---                                     |
| i32                   | enum                  | enum                  | str                                      | list[str]                               |
+============================================================================================================================================================+
| 0                     | SYSTEM                | EXECUTION_ENVIRONMENT | import json                              | null                                    |
|                       |                       |                       | from tool_sandbox.tools.contact import   |                                         |
|                       |                       |                       | add_contact, modify_contact,             |                                         |
|                       |                       |                       | remove_contact, search_contacts          |                                         |
|                       |                       |                       | from tool_sandbox.tools.setting import   |                                         |
|                       |                       |                       | get_cellular_service_status,             |                                         |
|                       |                       |                       | get_current_location, get_wifi_status,   |                                         |
|                       |                       |                       | set_cellular_service_status,             |                                         |
|                       |                       |                       | set_wifi_status                          |                                         |
|                       |                       |                       | from tool_sandbox.tools.messaging        |                                         |
|                       |                       |                       | import search_messages,                  |                                         |
|                       |                       |                       | send_message_with_phone_number           |                                         |
|                       |                       |                       | from tool_sandbox.tools.reminder import  |                                         |
|                       |                       |                       | add_reminder, modify_reminder,           |                                         |
|                       |                       |                       | remove_reminder, search_reminder         |                                         |
|                       |                       |                       | from tool_sandbox.tools.search_tools     |                                         |
|                       |                       |                       | import convert_currency,                 |                                         |
|                       |                       |                       | knowledge_base_question_answering,       |                                         |
|                       |                       |                       | search_dictionary, search_holiday,       |                                         |
|                       |                       |                       | search_lat_lon,                          |                                         |
|                       |                       |                       | search_location_around_lat_lon,          |                                         |
|                       |                       |                       | search_point_of_interest_around_lat_lon, |                                         |
|                       |                       |                       | search_stock,                            |                                         |
|                       |                       |                       | search_weather_around_lat_lon            |                                         |
|                       |                       |                       | from tool_sandbox.tools.user_tools       |                                         |
|                       |                       |                       | import end_conversation                  |                                         |
|                       |                       |                       | from tool_sandbox.tools.utilities        |                                         |
|                       |                       |                       | import datetime_info_to_timestamp,       |                                         |
|                       |                       |                       | get_current_timestamp,                   |                                         |
|                       |                       |                       | seconds_to_hours_minutes_seconds,        |                                         |
|                       |                       |                       | shift_timestamp, timestamp_diff,         |                                         |
|                       |                       |                       | timestamp_to_datetime_info,              |                                         |
|                       |                       |                       | unit_conversion                          |                                         |
|                       |                       |                       |                                          |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 1                     | SYSTEM                | AGENT                 | Don't make assumptions about what values | null                                    |
|                       |                       |                       | to plug into functions. Ask for          |                                         |
|                       |                       |                       | clarification if a user request is       |                                         |
|                       |                       |                       | ambiguous.                               |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 2                     | SYSTEM                | USER                  | You are no longer an assistant. Assume   | null                                    |
|                       |                       |                       | that you are a User talking to a virtual |                                         |
|                       |                       |                       | assistant. Answer any question the       |                                         |
|                       |                       |                       | virtual assistant asks you accurately.   |                                         |
|                       |                       |                       | You are a lazy user, so be less verbose  |                                         |
|                       |                       |                       | and only provide 1 piece of information  |                                         |
|                       |                       |                       | at a time. Keep trying to ask the        |                                         |
|                       |                       |                       | assistant to complete the task when it   |                                         |
|                       |                       |                       | claims it couldn't do so by providing    |                                         |
|                       |                       |                       | more instructions. Ask it to use the     |                                         |
|                       |                       |                       | tools it has access to to resolve any    |                                         |
|                       |                       |                       | issues it encountered at least 5 times.  |                                         |
|                       |                       |                       | Use only the information provided. Do    |                                         |
|                       |                       |                       | not make up false information. DO NOT    |                                         |
|                       |                       |                       | fall back to assistant behavior. When    |                                         |
|                       |                       |                       | you feel the assistant have completed    |                                         |
|                       |                       |                       | your task, or it still cannot complete   |                                         |
|                       |                       |                       | the request after 5 tries, use the       |                                         |
|                       |                       |                       | provided tool named `end_conversation`   |                                         |
|                       |                       |                       | to stop the conversation. The task you   |                                         |
|                       |                       |                       | would like to complete is: Send a        |                                         |
|                       |                       |                       | message to Fredrik Thordendal saying:    |                                         |
|                       |                       |                       | How's the new album coming along         |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 3                     | USER                  | AGENT                 | Send a message to Fredrik Thordendal     | null                                    |
|                       |                       |                       | saying: "How's the new album coming      |                                         |
|                       |                       |                       | along." Resolve any issue by yourself.   |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 4                     | AGENT                 | EXECUTION_ENVIRONMENT | call_LbXHvh2I1ibGcoy89hHDhsWQ_parameters | ["{"tool_name": "search_contacts",      |
|                       |                       |                       | = {'name': 'Fredrik Thordendal'}         | "arguments": {"name": "Fredrik          |
|                       |                       |                       | call_LbXHvh2I1ibGcoy89hHDhsWQ_response = | Thordendal"}, "result": [{"person_id":  |
|                       |                       |                       | search_contacts(**call_LbXHvh2I1ibGcoy89 | "9e137f06-916a-5310-8174-cf0b7e9f7054", |
|                       |                       |                       | hHDhsWQ_parameters)                      | "name": "Fredrik Thordendal",           |
|                       |                       |                       | print(repr(call_LbXHvh2I1ibGcoy89hHDhsWQ | "phone_number": "+12453344098",         |
|                       |                       |                       | _response))                              | "relationship": "friend", "is_self":    |
|                       |                       |                       |                                          | false}]}"]                              |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 5                     | EXECUTION_ENVIRONMENT | AGENT                 | [{'person_id':                           | null                                    |
|                       |                       |                       | '9e137f06-916a-5310-8174-cf0b7e9f7054',  |                                         |
|                       |                       |                       | 'name': 'Fredrik Thordendal',            |                                         |
|                       |                       |                       | 'phone_number': '+12453344098',          |                                         |
|                       |                       |                       | 'relationship': 'friend', 'is_self':     |                                         |
|                       |                       |                       | False}]                                  |                                         |
|                       |                       |                       |                                          |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 6                     | AGENT                 | EXECUTION_ENVIRONMENT | call_oHPoWYuTxkuKRojfGI5Ro4ML_parameters | null                                    |
|                       |                       |                       | = {'phone_number': '+12453344098',       |                                         |
|                       |                       |                       | 'content': "How's the new album coming   |                                         |
|                       |                       |                       | along."}                                 |                                         |
|                       |                       |                       | call_oHPoWYuTxkuKRojfGI5Ro4ML_response = |                                         |
|                       |                       |                       | send_message_with_phone_number(**call_oH |                                         |
|                       |                       |                       | PoWYuTxkuKRojfGI5Ro4ML_parameters)       |                                         |
|                       |                       |                       | print(repr(call_oHPoWYuTxkuKRojfGI5Ro4ML |                                         |
|                       |                       |                       | _response))                              |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 7                     | EXECUTION_ENVIRONMENT | AGENT                 | Traceback (most recent call last):       | null                                    |
|                       |                       |                       |   File "<string>", line 2, in <module>   |                                         |
|                       |                       |                       | File "/opt/anaconda3/envs/tool-sandbox/ |                                         |
|                       |                       |                       | lib/python3.9/site-packages/decorator.py |                                         |
|                       |                       |                       | ", line 232, in fun                      |                                         |
|                       |                       |                       | return caller(func, *(extras + args),    |                                         |
|                       |                       |                       | **kw)                                    |                                         |
|                       |                       |                       | File "ToolSandbox/                       |                                         |
|                       |                       |                       | tool_sandbox/common/utils.py", line      |                                         |
|                       |                       |                       | 361, in _f                               |                                         |
|                       |                       |                       |     result = f(*args, **kwargs)          |                                         |
|                       |                       |                       | File "ToolSandbox/                       |                                         |
|                       |                       |                       | tool_sandbox/tools/messaging.py", line   |                                         |
|                       |                       |                       | 51, in send_message_with_phone_number    |                                         |
|                       |                       |                       | raise ConnectionError("Cellular service  |                                         |
|                       |                       |                       | is not enabled")                         |                                         |
|                       |                       |                       | ConnectionError: Cellular service is not |                                         |
|                       |                       |                       | enabled                                  |                                         |
|                       |                       |                       |                                          |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 8                     | AGENT                 | EXECUTION_ENVIRONMENT | call_AbZtI4fkAAUwoonIDbcW2Vu3_parameters | ["{"tool_name":                         |
|                       |                       |                       | = {'on': True}                           | "set_cellular_service_status",          |
|                       |                       |                       | call_AbZtI4fkAAUwoonIDbcW2Vu3_response = | "arguments": {"on": true}, "result":    |
|                       |                       |                       | set_cellular_service_status(**call_AbZtI | null}"]                                 |
|                       |                       |                       | 4fkAAUwoonIDbcW2Vu3_parameters)          |                                         |
|                       |                       |                       | print(repr(call_AbZtI4fkAAUwoonIDbcW2Vu3 |                                         |
|                       |                       |                       | _response))                              |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 9                     | EXECUTION_ENVIRONMENT | AGENT                 | None                                     | null                                    |
|                       |                       |                       |                                          |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 10                    | AGENT                 | EXECUTION_ENVIRONMENT | call_5GE8RMyJbqoNWXIPJZbbq7L9_parameters | ["{"tool_name":                         |
|                       |                       |                       | = {'phone_number': '+12453344098',       | "send_message_with_phone_number",       |
|                       |                       |                       | 'content': "How's the new album coming   | "arguments": {"phone_number":           |
|                       |                       |                       | along."}                                 | "+12453344098", "content": "How's the   |
|                       |                       |                       | call_5GE8RMyJbqoNWXIPJZbbq7L9_response = | new album coming along."}, "result":    |
|                       |                       |                       | send_message_with_phone_number(**call_5G | "8a0ce99b-f2ee-4c47-9bb5-54e379b2233a"} |
|                       |                       |                       | E8RMyJbqoNWXIPJZbbq7L9_parameters)       | "]                                      |
|                       |                       |                       | print(repr(call_5GE8RMyJbqoNWXIPJZbbq7L9 |                                         |
|                       |                       |                       | _response))                              |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 11                    | EXECUTION_ENVIRONMENT | AGENT                 | '8a0ce99b-f2ee-4c47-9bb5-54e379b2233a'   | null                                    |
|                       |                       |                       |                                          |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 12                    | AGENT                 | USER                  | Message has been successfully sent to    | null                                    |
|                       |                       |                       | Fredrik Thordendal asking: "How's the    |                                         |
|                       |                       |                       | new album coming along."                 |                                         |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 13                    | USER                  | EXECUTION_ENVIRONMENT | end_conversation()                       | ["{"tool_name": "end_conversation",     |
|                       |                       |                       |                                          | "arguments": {}, "result": null}"]      |
|-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------|
| 14                    | EXECUTION_ENVIRONMENT | USER                  |                                          | null                                    |
+-----------------------+-----------------------+-----------------------+------------------------------------------+-----------------------------------------+
```

`milestone_mapping` contains a dictionary of `milestone_indx: (corresponding_turn_index, milestone_similarity)`
```json
{
   "name": "send_message_with_contact_content_cellular_off",
   "categories": [
       "STATE_DEPENDENCY",
       "MULTIPLE_TOOL_CALL",
       "SINGLE_USER_TURN",
       "NO_DISTRACTION_TOOLS"
   ],
   "similarity": 0.9706467684812784,
   "turn_count": 12,
   "milestone_mapping": {
       "1": [
           4,
           1.0
       ],
       "0": [
           9,
           1.0
       ],
       "2": [
           11,
           1.0
       ],
       "3": [
           12,
           0.8825870739251136
       ]
   }
}
```


## Citation

To cite _ToolSandbox_:
```text
@misc{lu2024toolsandboxstatefulconversationalinteractive,
      title={ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities},
      author={Jiarui Lu and Thomas Holleis and Yizhe Zhang and Bernhard Aumayer and Feng Nan and Felix Bai and Shuang Ma and Shen Ma and Mengyu Li and Guoli Yin and Zirui Wang and Ruoming Pang},
      year={2024},
      eprint={2408.04682},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2408.04682},
}
```
