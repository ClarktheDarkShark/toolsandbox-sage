# Paper experiment contract

This file is the release contract for the experiment reported by the current
dissertation. It distinguishes the immutable reference evidence from code
cleaned for public release. A cleanup is acceptable only when it preserves this
contract; newer diagnostics and experimental branches are not substitutes for
the study below.

## Identity and evidence

| Item | Authoritative record |
|---|---|
| Current manuscript | `praxis-paper` commit `eb444d678cf7ad32ec373f496359e2ef5f395e99`, tree `d6fe3d1d000fb314366e1c5b818463c89ed92dd5` |
| Scientific runtime | commit `4ce1c6de0ab36dd59e1a319f4e56e298133f4a79`, tree `4640019c7a054d4af6a500e7327ebbd0a507bfc5` |
| Final reporting checkpoints | base reporting commit `692af7f`; current H1--H3 reconstruction code at `fde58d3a01711991e9c74783293768d6fbb6b0fb` and dashboard presentation at `04479ca30fe4f0c33984a5191cf1409793a0275f`. These postdate the runs and do not alter their trajectories. |
| Selected cohort | `chapter4_final_policy_online_frozen_20260911_4ce1c6d`; online `rep01`, `rep02`, `rep03`, `rep04r1`, `rep05`--`rep10`; frozen `rep01`--`rep04`, `rep05r1`, `rep06`--`rep10` |
| Selection rule | Integrity only. Online `rep04` and frozen `rep05` remain preserved but are excluded because each contains one runtime exception. The replacements were selected without consulting performance. |
| Selected-cohort manifest | SHA-256 `8cd359bebdc0f3576643d6d4850f0abe09fd3c05dafd50a62fc07d62c6425192` |

The reference version is the runtime and selected artifacts above. The control
arm is the matched non-learning agent described below. The treatment arm is
policy-directed SAGE. The cleaned version is the public-release branch produced
from this contract; it is not a new experimental condition.

## Population and execution

- Benchmark: all 1,032 ordered ToolSandbox tasks in
  `docs/sage_protocol/manifests/v2_1_formal_1000_full_benchmark.json`.
- Benchmark SHA-256: `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`.
- Ordered task-name SHA-256:
  `fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176`.
- Repetitions: ten independently evolved online-build pairs followed by ten
  paired frozen-registry pairs. Each pair contains 1,032 matched control tasks
  and 1,032 SAGE tasks. Control and SAGE run concurrently in isolated processes.
- ToolSandbox clock: Unix timestamp `1784832588`; timezone
  `America/New_York`.
- External service input: read-only sanitized RapidAPI fixture at
  `artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json`,
  SHA-256 `eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f`.
- Current-paper reconstruction uses 10,000 bootstrap iterations, 20,000
  requested randomization iterations, and analysis seed `20260730`. For ten
  runs, the sign-flip calculation exhausts all assignments.

The online treatment starts each repetition with an empty run-local registry.
It may generate, repair, validate, admit, route, invoke, retain, suppress, and
reuse tools as tasks proceed in the fixed benchmark order. The frozen phase
copies the final registry from the matching online repetition and disables tool
generation and candidate repair. Frozen registries are immutable during their
paired evaluations. No registry, learned state, or task output crosses between
replications.

## Arms, models, prompts, and tools

The control and treatment use the same `gpt-4o-mini` actor, simulated user,
policy-aware actor wrapper, native ToolSandbox inventory, task order, fixed
clock, fixture, harness, and evaluator. The control has no generated registry,
generation, routing of generated tools, or lifecycle learning. The treatment
adds the complete SAGE mechanism: visible-context inadequacy classification,
model-authored generation and repair, validation, registry/lifecycle handling,
bounded routing, generated-tool execution, and the policy-directed actor.

The policy-directed actor is part of the treatment. Its policy messages,
ordered selector cascade, schema filtering, and named `tool_choice` requests
must not be described as natural model tool selection. Diagnostic force-call
variables are prohibited.

All three model roles use the unversioned provider identifier
`gpt-4o-mini`. The runtime source configures SAGE generation requests with its
default temperature of `0`, while actor and user requests omit temperature.
The artifacts do not independently persist numeric temperature, `top_p`, seed,
or output-token parameters, so the source tree and recorded generation-settings
digest—not a reconstructed parameter list—are authoritative for those request
semantics. The runtime tree is likewise authoritative for prompt bytes, native
tool schemas, generated-tool validation, ordering, serialization, and stopping
behavior. Online registry contents are outputs, not preloaded inputs; each
frozen repetition uses only its paired online registry.

## Retry, timeout, cache, and state policy

The launcher pins OpenAI client retries to 5, wrapper transient delays to 1 and
3 seconds, ToolSandbox transient scenario attempts to 4, actor/user request
timeout to 120 seconds, and generation timeout to 600 seconds. Failed or partial
publication rows are not resumed. A technical failure is preserved and a new
replacement run receives a distinct identity.

Fresh live controls are mandatory. The control baseline cache is off; cached
control tasks, repository-wide response replay, persistent generation-output
replay, SAGE task caching, cross-run failure memory, and diagnostic tool forcing
are prohibited. Within-run generator contract/repair-analysis memoization and
provider-managed implicit prompt-prefix caching are allowed and recorded.
Online reflection consumes the exact fresh same-task control row. The launcher
fails closed on missing or duplicate rows, cache use, source/environment drift,
runtime exceptions, or failure to open Task Compare before model execution.

## Evaluation and reported claims

The primary task metric is route-independent outcome completion in `[0,1]`.
Canonical/reference similarity is descriptive only and is never a performance,
hypothesis, or release gate. Minefield violations set the task outcome to zero.

- **H1, outcome lift:** audited `sage_outcome_contracts_v9` on all 1,032 tasks
  per online repetition (10,320 matched task pairs). Support requires relative
  lift of at least 10%, positive lower bounds for both the two-way run/task and
  run-cluster 95% target-contrast intervals, and exact run-level sign-flip
  `p < .05` for `SAGE - 1.10 * control`.
- **H2, repair and later reuse:** among candidates with an initial validation
  failure and at least one autonomous repair attempt, the repair-admission rate
  and its run-cluster 95% lower bound must exceed 50%, with run-level sign-flip
  `p < .05`; at least 90% of admitted repaired tools must be invoked on a later
  task, and the run-cluster 95% lower bound for that later-reuse rate must be at
  least 90%.
- **H3, cross-family use:** more than 50% of accepted generated-tool instances
  must be invoked on a later task from a semantic family different from the
  actual birth task's family; the run-cluster 95% lower bound must exceed 50%
  and the run-level sign-flip test must have `p < .05`.

The historical `sage_paper_outcome_contracts_v1` value on the exact ordered
800-task non-null subset is retained only for comparison with the earlier paper
analysis. It is never pooled with v9.

The selected campaign's run-time statistical plan used the earlier hypothesis
framing (frozen retention, outcome lift, and a descriptive called-task
association). The current repair/reuse H2 and cross-family H3 definitions and
decision rules were committed on 2026-09-21, after the selected runs completed.
Their inputs are immutable, their joins and calculations are reproducible, and
the manuscript reports them as hypotheses, but the historical H2/H3 analyses
are retrospective rather than preregistered. This provenance discrepancy must
not be hidden. A new campaign executed after this contract tests these fixed
rules prospectively.

Reference results are: H1 `0.586176 -> 0.783543` (`+33.67%`); H2 `105/161`
repaired and admitted (`65.2%`, 95% CI `[60.5%, 70.1%]`, `p=.004`) and
`105/105` reused later; H3 `164/285` used across families (`57.5%`, 95% CI
`[56.2%, 58.8%]`, `p=.002`). Supporting frozen gain retention is `96.28%`
with 95% CI `[92.54%, 100.01%]`. All 20 selected executions contain 1,032
tasks per arm, fresh controls, and zero runtime exceptions.

## Environment, artifacts, and interfaces

- CPython 3.12.7 on Darwin arm64; the publication lock has SHA-256
  `5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`.
- The 108 external distributions have aggregate SHA-256
  `006191cd1efca9e244c6b5d6fb6a8c91fb95c279959cc91c9eada316f904fc9d`.
- `scripts/run_native_action_4omini_ab.sh` is the single-pair entry point;
  `scripts/run_chapter4_evidence_campaign.py` prepares, runs, and verifies the
  ten-pair campaign.
- Required outputs include protocol/study manifests, per-task results and
  traces, tool-birth/validation/repair/routing/reuse/lifecycle ledgers, registry
  manifests, usage and outcome summaries, Task Compare data/HTML, aggregate
  Chapter 4 data/HTML, and manuscript table images.
- Task Compare must display partial, failed, and completed runs without treating
  missing values as zero. The Chapter 4 evolution report must recompute H1--H3
  from the selected raw cohort rather than from hand-entered manuscript values.

The current-paper reconstruction command is:

```bash
python scripts/build_chapter4_evolution_dashboard.py \
  --repo-root . \
  --campaign-manifest artifacts/chapter4_evidence/chapter4_final_policy_online_frozen_20260911_4ce1c6d/technical_replacement/final_selected_cohort/selected_cohort_manifest.json \
  --output-dir <new-immutable-directory> \
  --bootstrap-iterations 10000 \
  --randomization-iterations 20000 \
  --seed 20260730
python scripts/render_chapter4_evolution_tables.py \
  --data <new-immutable-directory>/chapter4_evidence_data.json \
  --output-dir <new-immutable-table-directory>
```

Every reconstruction must record the selected-manifest hash, analysis commit
and script hashes, command, UTC time, and hashes of the output JSON, HTML, and
images. The older `final_selected_cohort/dashboard/chapter4_evidence_data.json`
uses the superseded hypothesis framing and is not authoritative for current H2
or H3. The protected reference reconstruction is recorded in local artifact
`current_paper_evolution_20260924_04479ca/reconstruction_receipt.json`, SHA-256
`e4455a6405ef3ab6a4a94e1cf95275f31ed53f77dac3dc79ab756419647fb38f`.

## Cleanup acceptance

Before a live campaign, the cleaned tree must pass input/environment checks,
the full retained unit/integration suite, deterministic artifact/report
regeneration, package installation in an isolated checkout, and browser checks
for Task Compare plus the Chapter 4 dashboard. Protected prompt/schema/evaluator
bytes and ordered behavior must remain unchanged unless a deterministic
reference comparison proves equivalence.

The final release candidate must then complete one strict 1,032-task online
sample satisfying `publication_validation_thresholds_v3.json`, followed by ten
online and ten paired frozen executions under the integrity rules above. There
is no post-hoc cleanup tolerance: deterministic values must match exactly;
stochastic results must satisfy the pre-existing H1--H3 decision rules and the
single-sample no-regression gate. Any unexplained mismatch is a failed release
gate, not grounds to alter the evaluator, task set, or thresholds.
