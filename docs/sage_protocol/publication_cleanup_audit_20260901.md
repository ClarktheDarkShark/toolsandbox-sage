# SAGE Publication Cleanup Audit — 2026-09-01

## Decision

**AUDIT COMPLETE; REMOVAL AWAITS APPROVAL.** The protected paper campaign and
its active execution path have been reconstructed. No production source was
deleted or rewritten during this audit.

The repository is not yet reproducible from a clean checkout. Before removing
more code, the current validated source must be checkpointed and the paper
inputs, launcher, environment, and baseline must be made immutable. The
approval groups below separate that publication repair from low-risk deletion,
medium-risk simplification, and high-risk scientific logic that should remain.

## Executive Findings

1. The paper evidence is a **10-pair campaign**, not ten ordinary executions:
   ten independent online-build runs and ten paired frozen-registry runs. Each
   candidate arm executed all 1,032 tasks, for 20,640 candidate task executions.
2. The preserved artifacts support exact reanalysis of the reported numbers.
   They do not support an exact clean-checkout rerun because the campaign used
   three dirty source trees, its launcher is missing, key source and data are
   untracked or ignored, and live `gpt-4o-mini` calls were not seeded or pinned
   to a dated model snapshot.
3. The current worktree already contains two large, validated cleanup passes.
   They removed 22,070 non-dashboard production lines and passed two full
   1,032-task online-build gates, but these changes are still uncommitted.
4. The baseline called “v140” in the campaign is a selectively enriched hybrid:
   957 tasks use one v140 record and 75 tasks average three records. This raises
   the outcome baseline from 0.452803 to 0.457342. The same hybrid values also
   informed online self-evolution reflection decisions. Using v140 alone would
   increase the main outcome point-estimate lift from about 73.9% to about
   75.7%, so the hybrid did not inflate that headline. Nevertheless, provenance,
   unequal replication, cache-conditioned online behavior, intervals, tests,
   and all final hypothesis decisions require a strict fresh-control rerun.
5. The highest-value safe reductions are post-campaign custom-task and CyberGym
   products, dead compatibility surfaces, old runner modes, unused model
   backends, stale campaign-status machinery, and historical scripts/docs that
   should move to an archive.
6. The large actor, classifier, generator, online-birth, validation, and routing
   modules are result-critical. A prior attempt to replace them with a trimmed
   runtime caused a measured outcome regression. They should be split and
   documented, not behaviorally reduced, until stronger deterministic locks and
   branch coverage exist.

## Protected Paper Campaign

### Authoritative evidence

- Campaign ID: `chapter4_final_claim_10x_20260730`
- Campaign manifest:
  `artifacts/chapter4_evidence/chapter4_final_claim_10x_20260730/campaign_manifest.json`
- Final evidence data:
  `outputs/chapter4_evidence/chapter4_final_claim_10x_20260730/dashboard/chapter4_evidence_data.json`
- Benchmark:
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`
- Benchmark SHA-256:
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`
- Model for actor, user, generation, and repair: `gpt-4o-mini`
- Fixed ToolSandbox time: `1784832588`
- Online mode: `online_build_full`, empty registry, generation and repair on
- Frozen mode: `full_benchmark`, paired registry, generation and repair off
- Base tools: upstream ToolSandbox policy
- Controls: strict task-level hybrid cached baseline; no live controls in the
  20 arms
- Online reflection control: values read from the same hybrid cache
- SAGE task cache: off
- Repository whole-response replay cache: off (provider prompt-prefix token
  reuse was not treated as response replay)
- Scenario-name birth and routing: disabled
- Synthetic bridge completion: disabled
- Diagnostic force calls: disabled
- Statistical analysis: seed `20260730`, 10,000 bootstrap iterations, 20,000
  randomization iterations

Runs 1–5 were preserved from the July 23 replication root. Runs 6–10 and all
frozen passes were completed in the July 30 campaign. Frozen replication 8
stopped after 687 tasks and resumed from that checkpoint, so resume support is
part of the historical execution path and must not be treated as dead code.

### Final results

| Metric | Baseline | Online SAGE | Frozen SAGE |
|---|---:|---:|---:|
| Canonical/reference mean | 0.733488 | 0.797953 | 0.806318 |
| Outcome/task-completion mean | 0.457342 | 0.795407 | 0.796693 |
| Online outcome absolute gain | — | +0.338065 | — |
| Online outcome relative lift | — | +73.9% | — |
| Frozen gain retention | — | — | 100.4% |

The online outcome range was 0.776052–0.809509 and the canonical score range
was 0.787598–0.806645. All 20 runs completed their 1,032 tasks, all protocol
gates passed, and the final evidence reports zero runtime exceptions.

| Rep | Online canonical | Online outcome | Frozen canonical | Frozen outcome |
|---:|---:|---:|---:|---:|
| 1 | 0.791434 | 0.778770 | 0.798751 | 0.792143 |
| 2 | 0.796437 | 0.798097 | 0.804042 | 0.799951 |
| 3 | 0.799026 | 0.801611 | 0.799549 | 0.812550 |
| 4 | 0.796598 | 0.806536 | 0.801242 | 0.799149 |
| 5 | 0.787598 | 0.809509 | 0.812739 | 0.804450 |
| 6 | 0.800992 | 0.802548 | 0.805007 | 0.790481 |
| 7 | 0.798763 | 0.776052 | 0.812616 | 0.793256 |
| 8 | 0.806645 | 0.799414 | 0.808655 | 0.788433 |
| 9 | 0.799600 | 0.787253 | 0.809132 | 0.804822 |
| 10 | 0.802436 | 0.794280 | 0.811449 | 0.781696 |

### Reproducibility classes

| Reproduction target | Current status |
|---|---|
| Recompute the published statistics from preserved artifacts | Possible, if the exact untracked analysis source is preserved |
| Rerun the ten frozen registries | Structurally possible after packaging/input repair; identical stochastic trajectories are not guaranteed |
| Regenerate ten online registries and obtain the same point values | Not possible exactly with unseeded live calls to a floating model alias; only a statistical replication is defensible |
| Reproduce from a fresh clone today | Not possible |

## End-to-End Paper Execution Graph

```text
formal 1,032-task manifest + fixed clock + RapidAPI fixture
  -> campaign launcher and paired-run orchestration
  -> strict cached control synthesis
  -> ToolSandbox scenario resolution/execution
  -> OpenAI actor and user roles
  -> visible-context inadequacy classification
  -> online tool birth
       -> model-authored generation
       -> candidate repair
       -> AST/schema/runtime/negative/native-action validation
       -> registry persistence
  -> generated-tool routing and ToolSandbox injection
  -> actor selection, native side effects, scoring, reflection, checkpoints
  -> matched run metrics + contribution accounting + Task Compare export
  -> ten-pair Chapter 4 aggregation and inference
  -> evidence JSON/HTML
  -> manuscript tables and Chapter 4 text
```

### Runtime files to preserve

The following are directly on the protected execution path:

- `scripts/run_chapter4_evidence_campaign.py`
- the missing `scripts/run_native_action_4omini_ab.sh`, which must be
  reconstructed from archived commands
- `scripts/run_sage_protocol.py`
- `src/sage_ts/config/splits.py`
- `src/sage_ts/config/models.py`
- `src/sage_ts/config/openai_client.py`
- `src/sage_ts/adapters/role_factory.py`
- `src/sage_ts/adapters/toolsandbox_adapter.py`
- `src/sage_ts/adapters/sage_run_adapter.py`
- `src/sage_ts/adapters/openai_agent_adapter.py`
- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/orchestration/self_evolution_reflection.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/generation/tool_spec.py`
- `src/sage_ts/generation/complete_tools.py`
- `src/sage_ts/validation/ast_safety.py`
- `src/sage_ts/validation/schema_check.py`
- `src/sage_ts/validation/sandbox_validator.py`
- `src/sage_ts/validation/output_normalization.py`
- `src/sage_ts/registry/manifest.py`
- `src/sage_ts/registry/store.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/runtime/routing_scorer.py`
- `tool_sandbox` scenario, tool, execution-context, OpenAI-role, and evaluation
  code used by the formal manifest

### Evaluation and paper files to preserve

- `src/sage_ts/evaluation/control_baseline_cache.py`
- `src/sage_ts/evaluation/outcome_score.py`
- `src/sage_ts/evaluation/run_metrics.py`
- `src/sage_ts/evaluation/helper_contribution.py`
- `src/sage_ts/evaluation/llm_usage.py`
- `src/sage_ts/dashboard/exporters.py`, at least the Task Compare payload
- `src/sage_ts/dashboard/task_compare_template.py`
- `src/sage_ts/evaluation/chapter4_evidence.py`
- `src/sage_ts/dashboard/chapter4_evidence_template.html`
- `scripts/render_chapter4_evidence_tables.py`
- `docs/sage_protocol/chapter4_results_completed.tex`

## Publication-Critical Blockers

These are mandatory repairs before further cleanup is accepted as a publishable
release.

### P0.1 — Freeze a clean source state

Every study manifest names commit
`25466400ae48b4520a3d7cf914d9c85d3a512755`, but the campaign used three
different dirty source trees:

| Campaign wave | Recorded tree SHA-256 |
|---|---|
| Online replications 1–5 | `d6aad9bc350a3e6ba7389298d7ed66deaacdff54064fa4f4db5c15fd1463a928` |
| Online 6–10 and frozen 1–5 | `39214520a16a8d3273c8b91f3d0c41163d33d9ae6cd538839a2c31715ceb07bd` |
| Frozen 6–10 | `2528f26af5d3025feb7e62cc0a95620d044a2a5e42fac4fb75314c60fc35d5a0` |

The artifacts do not contain the patches that produced these hashes. The
current worktree is also heavily dirty: 81 tracked files have approximately
17,037 additions and 40,868 deletions, with many publication-critical files
untracked. A release checkpoint must preserve this state before any new edit.

Every online/frozen pair therefore crosses a recorded source-tree boundary:
replications 1–5 compare `d6aad9bc...` online code with `39214520...` frozen
code, and replications 6–10 compare `39214520...` online code with
`2528f26a...` frozen code. This is a potential confound for the H1 persistence
claim. It does not by itself show that the code difference caused the observed
retention, but the current artifacts cannot rule that out because the patches
are missing. The limitation must be disclosed, and the paired full release gate
should be rerun from one clean code commit.

### P0.2 — Restore one canonical launcher

`scripts/run_chapter4_evidence_campaign.py` invokes
`scripts/run_native_action_4omini_ab.sh`, but that file is absent from both the
worktree and Git history. Exact per-arm command files remain in the campaign
artifacts and are sufficient to reconstruct a single versioned command surface.

The replacement should expose five explicit operations:

1. `verify-inputs`
2. `run-online`
3. `run-frozen`
4. `analyze`
5. `render-paper`

### P0.3 — Retire the hybrid baseline from execution and publish sensitivity

The cache currently contains 1,182 complete records for 1,032 tasks:

- 957 tasks have one record;
- 75 tasks have three records;
- the extra 150 records came from four later targeted mechanism/validation
  controls;
- the paper lookup averaged every compatible record per task.

| Baseline form | Canonical mean | Outcome mean |
|---|---:|---:|
| Original June 12 v140 run | 0.7331747171 | 0.4528026205 |
| Hybrid baseline actually used | 0.7334883640 | 0.4573418739 |
| Difference | +0.0003136469 | +0.0045392534 |

With the paper's unchanged online SAGE mean of 0.7954070630, the v140-only
relative outcome lift is about 75.7%, compared with the reported 73.9%. The
hybrid therefore did not inflate the headline point estimate. This substitution
does not reconstruct how the online lifecycle would have evolved without its
hybrid-cache reflection comparisons; H1/H2/H3 intervals, tests, attribution,
and decisions remain invalid as final evidence and require a new campaign.

The corrected publication runner must prohibit baseline-cache construction and
lookup. Each arm must execute a complete fresh control first, and online
reflection must consume exactly one same-run fresh control row per task or fail
closed. The original v140 and expanded hybrid records remain frozen historical
analysis inputs only and are ineligible for new runs.

The campaign's recorded cache hash
`7c704d399bd665bc81041e0baa5d4a68c51a90a20cad9ce6f4ba215295a241d7`
hashes only `cache_manifest.json`; it does not hash the values. Current hashes
that should be recorded in the publication bundle are:

- `compact_records.jsonl`:
  `f572cc3f82a343bd561e0ffc63936564ab533c689b088cffbfca32175e2a55d0`
- `index.jsonl`:
  `ac0739b5040927ccd886d7bc6bb7ca2b7d150071d087f111b944d11faf9a902a`
- complete compact/index/records bundle:
  `8180d91eb6c5f23f231e8b61c65a2f2cc5ed6a8ba4d62a56f3e2637aaac995b7`

The paper must also state that “8,000 matched observations” means 800 task
names across ten SAGE replications against reused cached control values, not
8,000 independent control executions.

### P0.4 — Publish all ignored inputs

The release needs content-addressed copies or an archival-data DOI for:

- the baseline cache;
- all ten paired registries, including generated source, specs, validation
  evidence, and lifecycle state;
- the formal benchmark manifest;
- the sanitized RapidAPI response fixture;
- the final campaign manifest, per-run protocol manifests, comparisons, and
  compact statistical input data;
- the exact analysis and paper-rendering source.

The current RapidAPI fixture is ignored, has 85 entries, and has SHA-256
`4b3a8eca43fe8908330c7fc891597a8a418d3e109ff435726ec94e1177b2b05b`.
Older documentation records a different 71-entry fixture. The campaign did not
record which content hash it consumed.

### P0.5 — Lock the environment and model metadata

The current successful interpreter is Anaconda Python 3.12.7, while
`environment.yml` pins Python 3.9 and `pyproject.toml` advertises `>=3.9`.
`scripts/run_chapter4_evidence_campaign.py` uses `datetime.UTC`, requiring
Python 3.11 or later.

Selected declared/current versions also differ:

| Package | Declared | Current working environment |
|---|---:|---:|
| OpenAI | 1.17.0 | 2.37.0 |
| httpx | 0.27.2 | 0.28.1 |
| Pydantic | 2.7.4 | 2.13.4 |
| transformers | 4.41.2 | 5.7.0 |

The release needs a lockfile, a fresh-environment install test, platform and
Python metadata, a complete non-secret run configuration, and direct
declarations for runtime dependencies. Model calls should record the API model
identifier, system fingerprint when available, temperature, seed when
supported, retries, and request metadata. A floating `gpt-4o-mini` alias means
future reruns remain distributional rather than bitwise reproductions.

The historical protocol manifests also redact
`SAGE_MAX_REJECTIONS_PER_TOOL_KEY`, so that run-affecting value must be recovered
or explicitly redefined in the versioned paper configuration.

### P0.6 — Make analysis and paper rendering single-source

`scripts/render_chapter4_evidence_tables.py` hard-codes several H1/H2/H3
values, confidence intervals, integrity counts, failure counts, input/output
paths, and macOS font paths. It can silently disagree with regenerated evidence.
Every reported number should be read from a versioned analysis data schema, and
the renderer should accept paths and portable fonts as arguments.

### P0.7 — Repair the repository interface

- `make compile` fails because it references two removed `src/sage_research`
  files.
- `make full` and `make full500` pass removed CLI flags.
- `README.md` calls an older Chapter 3 v061 run canonical and documents stale
  behavior and commands.
- `pyproject.toml` still identifies the package as upstream `tool_sandbox`
  version 0.0.1 with upstream project metadata.
- bare `pytest` resolves to a different Homebrew Python and fails collection;
  `python -m pytest` under the project interpreter is the working command.

## Existing Validated Cleanup in the Worktree

The current uncommitted source already includes two cleanup increments that
should be preserved as the starting checkpoint, not recreated.

| Increment | Non-dashboard production reduction | Full SAGE canonical | Full SAGE outcome | Status |
|---|---:|---:|---:|---|
| 2026-08-01 legacy-path cleanup | 65,615 -> 46,196 (-19,419) | 0.8022 | 0.8073 | Passed 1,032 tasks, zero runtime exceptions |
| 2026-08-02 optional-branch cleanup | 46,196 -> 43,545 (-2,651) | 0.7986 | 0.7900 | Passed 1,032 tasks, zero runtime exceptions |

The second pass also locked all 1,810 classifier observations and all 1,810
generation and repair prompts exactly:

- generation aggregate SHA-256:
  `a9e67f03f58c37838d36af7d35c660999bd09459f11afe24e984cb46315e6534`
- repair aggregate SHA-256:
  `1604bcebc4c4037ffd00b0383889a54b0c2f5ff0851eaa7da1de9f8d1f02eb5d`

These runs support engineering-level distributional equivalence to the
protected ten-run range. They do not supply confirmatory hypothesis evidence
because their online lifecycle also used hybrid-cache reflection comparisons,
and they do not solve the clean-checkout provenance problem because the cleanup
is not yet a committed, installable release.

## Cleanup Approval Matrix

### R1 — Immediate low-risk removal

Approve these together after the P0 checkpoint is created.

| ID | Candidate | Evidence | Approximate reduction | Gate |
|---|---|---|---:|---|
| R1.1 | Custom-task product: `src/sage_ts/custom_tasks`, custom-task runner/server/template, and tests | Added after the July campaign; outside paper imports except dashboard links | 8,552 lines | Remove dashboard links; compare Task Compare data/render |
| R1.2 | `src/sage_cybergym`, its runner, and tests | Separate post-campaign adapter with no paper-run import | 1,627 lines | Core import and test suite |
| R1.3 | Statically unreferenced symbols and unused locals | No runtime/test callers | Small | compile, Ruff, retained unit suite |
| R1.4 | `recency_reduced` base-tool policy | All paper runs used `upstream` | About 50–100 lines plus plumbing | Scenario/tool schema digest |
| R1.5 | Routing-evidence CLI/env/path plumbing | Current routing scorer does not read it; final path used disabled | Tens of lines | Routed-bundle digest |
| R1.6 | `SAGE_COMPLETE_TOOLS_MODE` compatibility switch only | Current native-action behavior is specification-driven | Tens of lines | Native-action tests and prompt digest |
| R1.7 | Promotion-only registry gate and CLI | Final admission uses candidate gate; campaign copies accepted registries | About 380 lines | Candidate admission/integration suite |
| R1.8 | Test-only `runtime/tool_invoker.py` | Paper executes through ToolSandbox injection | Small | Convert lifecycle test to real injection path |

R1.6 does **not** authorize removal of `complete_tools.py`, native-action
generation, validation, routing, actor policy, or side-effect execution. Those
are active scientific mechanisms.

Known dead definitions include:

- `scripts/migrate_registry.py:check_validation_proof`
- `src/sage_ts/dashboard/exporters.py:_extract_tool_names_from_trace`
- `src/sage_ts/generation/tool_generator.py:parse_generated_tool_json`
- `src/sage_ts/orchestration/checkpoints.py:write_json`
- `src/sage_ts/orchestration/online_birth.py:GeneratedToolRepairFactory`
- `src/sage_ts/runtime/toolsandbox_integration.py:retained_tool_visibility_policy_digest`

### R2 — Focused orchestration simplification

These candidates did not affect the final path, but they touch runner,
artifacts, or cache behavior and need exact deterministic comparison.

| ID | Candidate | Proposed final form | Risk/gate |
|---|---|---|---|
| R2.1 | Eighteen historical runner modes and auto matrices | One versioned paper config with explicit online/frozen commands and an optional task limit for smoke tests | Medium; compare manifest, task order, registry start, generation state |
| R2.2 | Multiprocessing parallel-arm branch | Remove from paper runner; strict cached controls made it inactive in every paper arm | Low-medium; retain separate baseline-builder command |
| R2.3 | General mutable control-cache modes | Prohibit cache use in the paper runner; retain historical snapshots only for offline sensitivity analysis | Medium; prove 1,032 live controls and exact one-to-one same-run reflection matching |
| R2.4 | Failure-memory integration | Remove from paper runtime after preserving the same empty prompt field during transition | Medium; exact prompts and candidate decisions |
| R2.5 | Protocol-gate registry rollback | Make gate analysis-only and preserve failed registries | Medium; passing path exact, failing path preservation test |
| R2.6 | Stale campaign status/task-plan framework | Minimal immutable provenance plus append-only lifecycle events | Low-medium; retain Task Compare event schema |
| R2.7 | Cohort/preflight development branches | Formal manifest hash and fixed quality checks; move exploratory builders to archive | Medium; exact 1,032 names/order/checksums |
| R2.8 | Duplicate OpenAI retry/config parsing | One client-policy module with role-specific timeout values | Low-medium; retry/timeout tests |
| R2.9 | Historical runtime compatibility shims | Offline artifact converter; one registry/runtime schema | Medium; round-trip all ten published registries |

The paper command asked for `--parallel-arms`, but the runner forced
`effective_parallel_arms=False` because all controls were cached. Removing this
branch from the paper runner therefore does not remove exercised behavior.

### R3 — OpenAI-only backend reduction

The paper uses the configurable OpenAI actor and user only. After changing
`role_factory.py` so it does not import `tool_sandbox.cli.utils`, remove or move
to an optional upstream extra:

- Anthropic roles;
- Cohere roles;
- Gemini roles;
- Gorilla roles;
- Hermes roles;
- Mistral roles and utilities;
- interactive CLI and unhelpful-agent implementations;
- their backend-specific tests and dependencies.

This removes roughly 4,154 role-source lines and permits removal of heavy
packages such as Anthropic, Vertex AI, Transformers, Hugging Face Hub, and
SentencePiece when no retained import needs them. Risk is medium because the
code is vendored upstream ToolSandbox. Preserve upstream attribution and an
untouched upstream reference, then verify all formal scenario checksums, role
construction, schemas, and core ToolSandbox execution.

Do not remove ToolSandbox scenarios, tools, execution environment, OpenAI role
semantics, scoring/evaluation, or RapidAPI fixture support.

### R4 — Dashboard and historical-repository reduction

Keep Task Compare and the Chapter 4 evidence dashboard. Remove or archive:

- standard dashboard and Task Focus UI if they are not manuscript dependencies;
- dashboard auto-server, browser opening, global latest pointers, and macOS
  `open` behavior;
- custom-task UI already included in R1;
- old live-dashboard patchers;
- phase/Praxis/token-reduction/alternate-launcher/registry-pack one-off scripts;
- obsolete manifests, keeping the formal 1,032-task manifest and one smoke
  subset;
- old run artifacts and reports from the active release tree.

Historical material should be preserved on a tag or archival data release,
not silently destroyed. The active publication repository should retain a
reproduction guide, final methods/results, limitations, licenses/attribution,
input checksums, statistical data, and manuscript-generating source.

Expected dashboard-only reduction after the custom-task removal is roughly
1,500–2,500 additional lines. The gate is equality of Task Compare JSON schema,
metrics, generated-tool summaries, trace links, and a rendered smoke test.

### R5 — High-risk modules: retain behavior

Do not approve behavioral deletion inside these files in the first publication
cleanup:

- `src/sage_ts/adapters/openai_toolsandbox_roles.py`
- `src/sage_ts/adequacy/inadequacy_classifier.py`
- `src/sage_ts/generation/tool_generator.py`
- `src/sage_ts/runtime/toolsandbox_integration.py`
- `src/sage_ts/orchestration/online_birth.py`
- `src/sage_ts/validation/output_normalization.py`
- `src/sage_ts/adapters/sage_run_adapter.py`
- `src/sage_ts/adequacy/candidate_gate.py`
- AST/schema/sandbox/native-action validation
- registry serialization and lifecycle reflection

These modules may be split into smaller, named components after behavior locks
exist. A June 2026 package-boundary cleanup removed actor guidance and handoff
behavior while leaving superficially similar flags; the next full run retained
positive lift but lost outcome quality and produced more side-effect incidents.
That is direct evidence that apparently verbose actor scaffolding is part of the
intervention.

Recommended structural refactors, performed one at a time:

1. Split the runner into immutable configuration, preflight, control synthesis,
   candidate execution, evidence export, and provenance.
2. Convert classifier dispatch and actor policy selection to ordered declarative
   rule tables while snapshotting order and outputs.
3. Separate runtime core, ToolSandbox adapter, paper analysis, and optional demos
   into explicit packages.
4. Replace run-affecting environment-variable matrices with a checked-in,
   versioned paper configuration and reject unknown overrides.
5. Add branch coverage for every rule reached by the 1,032-task manifest before
   removing any remaining branch.

## Validation Required After Approval

### Stage 1 — Preserve and build

1. Create a non-destructive source checkpoint of the current validated dirty
   tree and record its SHA-256.
2. Create a clean release branch/commit from that checkpoint.
3. Add a dependency lock and install the wheel into a fresh environment.
4. Make `compile`, `test`, `paper-online`, `paper-frozen`, `analyze`, and
   `render-paper` the supported interface.

### Stage 2 — Exact deterministic locks

Before spending API calls, require equality of:

- all 1,810 visible-context classifier observations;
- generation prompt aggregate SHA-256;
- repair prompt aggregate SHA-256;
- all 1,032 fresh control rows and their one-to-one same-run reflection use;
- all 1,032 scenario names, order, checksums, and transformed schemas;
- routed generated-tool bundles;
- normalization and native-action validation fixtures;
- registry serialization, loading, copying, and hashes;
- Chapter 4 statistics from the frozen preserved input data.

### Stage 3 — Tests and representative cohorts

1. Compile and run static checks.
2. Run the retained unit and integration suite with the locked project
   interpreter.
3. Run the established three 30-task cohorts from empty registries:
   generated-tool coverage, native-action/side-effect behavior, and
   recency/selection/answer behavior.
4. Require zero runtime exceptions and all predeclared cohort floors.

### Stage 4 — Full release gate

A “complete” release verification should be one paired experiment, not just one
online arm:

1. one fresh 1,032-task online build from an empty registry;
2. one 1,032-task frozen-registry run using that exact paired registry with
   generation, repair, and reflection disabled.

Compare the online result with the protected ten-run distribution rather than
requiring one stochastic point estimate to equal the mean. Require:

- all 1,032 tasks present and in order;
- protocol gate pass;
- zero runtime exceptions;
- outcome within the predeclared protected/no-inferiority boundary; canonical/reference similarity is report-only;
- accepted/called/reused-tool lifecycle evidence;
- audited generated-tool failures and side-effect alerts;
- a content-complete provenance manifest.

One pair is the cleanup release gate. Repeating the paper's inferential claim is
a separate 10-pair statistical replication and should not be described as a
single full run.

## Audit Checks Performed

- Reconciled all 20 campaign run roots and completion states.
- Read archived online and frozen commands.
- Traced runtime, registry, cache, evaluation, dashboard, and manuscript paths.
- Audited all 1,182 baseline records and their five source runs.
- Verified the current source compiles with the project Python.
- Ran a critical retained-path test slice: 139 passed.
- Confirmed `make compile` fails on stale paths.
- Confirmed bare `pytest` resolves to a different interpreter and fails
  collection, while `python -m pytest` is the working entry point.
- Ran targeted unused-import/name/local checks and identified only small cleanup
  findings in the protected scope.
- Did not launch a costly API-backed full run because removal has not yet been
  approved and the publication inputs are not yet frozen.

## Requested Approval

Recommended first execution scope:

1. **P0 — mandatory publication repair**
2. **R1 — immediate low-risk removal**
3. **R2 — focused runner/cache/artifact simplification**
4. **R3 — OpenAI-only backend reduction**
5. **R4 — Task-Compare-only dashboard and historical archive split**
6. **R5 — retain behavior; structural refactor only after locks**

Approval may be given by group or individual ID. The safest default is
`P0 + R1`, then rerun deterministic locks before beginning R2–R4.

**NEEDS_REVISION: freeze publication provenance and obtain explicit cleanup
approval before modifying the validated runtime.**
