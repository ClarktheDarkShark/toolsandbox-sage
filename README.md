# SAGE for ToolSandbox

This repository contains the production research implementation of SAGE used
with Apple's 1,032-task ToolSandbox benchmark. SAGE detects recurring capability
gaps, generates and validates reusable Python tools, retains accepted tools in a
registry, routes them to later tasks, and applies an actor policy that selects and
sequences the generated and native tools.

This release intentionally restores the **policy-directed** SAGE studied in the
paper. It does not claim that the base model naturally chooses generated tools.
The later natural-selection experiments are not part of this branch.

## What was restored

The ten paper runs all identified Git commit
`25466400ae48b4520a3d7cf914d9c85d3a512755`, but they were executed from dirty
working trees. The online runs record two distinct source-tree hashes:

- replications 1–5:
  `d6aad9bc350a3e6ba7389298d7ed66deaacdff54064fa4f4db5c15fd1463a928`
- replications 6–10:
  `39214520a16a8d3273c8b91f3d0c41163d33d9ae6cd538839a2c31715ceb07bd`

The corresponding patches were not preserved, so no Git checkout can honestly
be described as a byte-for-byte reconstruction of all ten executions. The code
in this branch instead uses commit
`5bf1a1a3377bb913cb11fdcd1228f18003300714` (tree
`718ef02a85f0490d7e4dbbec4192567a1bd10b9d`) as its algorithm donor. That is the
first clean, policy-only reconstruction validated against the paper runtime. Its
complete 1,032-task validation produced a paper-era-evaluator SAGE outcome of
0.7900, within the paper campaign's 0.7761–0.8095 range. That establishes
that the restored behavior is consistent with the historical range in one
engineering spot check; it does not establish replicated distributional
equivalence and is not presented as a current audited outcome. New runs report
two explicitly scoped outcome measurements: audited v9 over all 1,032 tasks and
the unchanged paper-era v1 evaluator over the exact ordered 800-task subset.
Only the latter is compared with historical paper values.

The accurate description for this release is therefore:

> Clean policy-runtime reconstruction validated by an in-range engineering
> spot check, with separately audited measurement and fail-closed run
> provenance.

The detailed historical audit is in
[`docs/sage_protocol/publication_cleanup_audit_20260901.md`](docs/sage_protocol/publication_cleanup_audit_20260901.md).
The final restoration boundary, mechanism inventory, and reproducible line
counts are recorded in
[`docs/sage_protocol/policy_production_release_20260908.md`](docs/sage_protocol/policy_production_release_20260908.md).

## Restored high-lift configuration

The restored high-lift configuration uses an external actor policy rather than
natural model selection. On each actor request the policy can:

1. add workflow-specific instructions derived from the visible conversation;
2. filter the routed generated-tool schemas to a small relevant set;
3. hide wrapped native-action schemas when a validated generated replacement is
   selected;
4. choose a generated, downstream native, completion, or recovery tool through
   a deterministic selector cascade; and
5. send a named OpenAI `tool_choice` for that step.

The model still supplies tool arguments, consumes results, and produces the user
response. The controller decides which tool the model must call at policy-covered
steps. Run manifests record `actor_selection_mode="policy"` explicitly.

The primary control is a matched non-learning control, not the untouched
ToolSandbox actor. Both arms use the same `sage_wrapped` policy actor and model;
the control receives no generated tools or tool-generation lifecycle, while the
SAGE arm does. Manifests record
`control_condition="matched_policy_wrapper_without_generated_tools"` and each
arm's runtime so this estimand cannot be confused with the separately available
pure-ToolSandbox diagnostic.

The other critical components are:

- visible-context inadequacy classification and candidate admission;
- online tool birth, model-authored generation, and repair;
- schema, AST, sandbox, held-out, and negative-applicability validation;
- registry storage, lifecycle reflection, and task-conditioned routing;
- native/generated ToolSandbox injection and execution;
- output normalization, reuse accounting, and outcome evaluation.

Generated-tool lifecycle failures now have enforced outcomes rather than only
diagnostic labels. Direct contract or execution failures enter a bounded
repair-and-validation loop; failed replacements are retired. Repeatedly harmful
routes are narrowed, repeated non-adoption triggers metadata repair, and every
replacement must pass a future-task canary before promotion. Whole-task outcome
alone remains an alarm because it cannot reliably identify which co-called tool
caused the failure. The prospective protocol, evidence boundary, contact-tool
use case, and validation ladder are documented in
[`docs/sage_protocol/generated_tool_lifecycle_repair_20260913.md`](docs/sage_protocol/generated_tool_lifecycle_repair_20260913.md).

The lifecycle is fail-closed at two research-integrity boundaries. Generation
uses synthetic public examples and strips held-out validator cases before model
inference; repair requests cannot contain task/scenario identifiers, expected
answers, target state, evaluator traces, outcome values, or success flips.
Under ToolSandbox name scrambling, classification, routing, and policy choices
derive only from the names and schemas exposed to the actor. Ambiguous opaque
tools remain opaque; the private alias map is reserved for execution after a
visible tool has already been selected.

These mechanisms remain intact. Cleanup removed obsolete reporting, cohort,
registry-migration, cache-accounting, and dashboard patch utilities that are not
reachable from the production runner. Chapter 4 aggregation remains available
under `scripts/research/`, outside the installed `sage_ts` package.

## Outcome measurement and behavioral compatibility

The paper-era outcome evaluator influenced the historical registry trajectory,
so it remains available as a separately named comparability endpoint. The
prospective repair lifecycle must not mix two reward definitions across tasks,
however. Reporting and new lifecycle decisions therefore use one audited
endpoint, while the legacy measurement is diagnostic only:

- `outcome_similarity` is computed by audited v9 for all 1,032 tasks. It is the
  current same-run outcome endpoint, supplies the control-to-SAGE lift gate,
  is subject to the adaptive technical-readiness requirement that the SAGE mean
  be strictly greater than `0.80`, and is the prospective birth, routing,
  repair, and canary feedback signal;
- `online_feedback_outcome_similarity` is computed by paper-era v1 on its exact
  ordered 800-task applicability subset. It is the only endpoint compared with
  the historical paper range, but it does not control the prospective repair
  lifecycle; and
- a missing audited outcome is an integrity failure; the paper-era value never
  fills that gap. Canonical score deltas can inform descriptive analysis but are
  never a release, repair, canary, or paper-result gate.

These are post-task, evaluator-derived scalar feedback signals. Benchmark
answer and state targets are used by the evaluators, but raw targets, expected
answers, and evaluator traces are not provided to the actor or generated tools
before or during that task. Both evaluator identities and hashes are written to
the run artifacts. This split preserves the studied policy behavior without
comparing incompatible task sets or evaluator versions.

The latest complete strict pair, executed immediately before the v9 selector
correction, produced `0.586240 -> 0.780362` on audited v8. Exact offline v9
replay of all potentially affected message-recency trajectories changed one
SAGE task from `1` to `0`, giving `0.586240 -> 0.779393` across 1,032 tasks
(`+0.193152` absolute; `+32.95%` relative). On the exact paper-comparable 800
tasks, the unchanged v1 endpoint was `0.503964 -> 0.799612`, above both the
historical mean (`0.795407`) and minimum (`0.776052`). This is a successful
engineering sample, not a substitute for the final ten-run inference.

## Historical cache limitation

The successful July campaign used a strict hybrid control cache, and those
cached rows also informed online reflection. The cache contained 1,182 records
for 1,032 tasks, including 75 triplicated tasks. Consequently, the archived ten
runs are evidence of the policy system under that cache-conditioned protocol,
not clean fresh-control causal evidence.

The legacy cache reader remains in the source only to preserve historical
behavior and artifact compatibility. It is ineligible for new publication
runs. The canonical launcher enforces a fresh control and records zero cached
task/control/result reuse.

## Installation

The frozen publication environment is CPython 3.12.7 on Darwin/arm64. Create it
from the exact dependency lock:

```bash
./scripts/bootstrap_env.sh .venv-publication
source .venv-publication/bin/activate
python scripts/verify_publication_environment.py
```

The verifier checks the Python/platform identity, exact external distributions,
editable repository metadata, and isolated imports of both `sage_ts` and
`tool_sandbox` from this checkout. Set `OPENAI_API_KEY` in the environment before
a live run. A local `.secrets/env.sh` is supported and must not be committed.

## Verify the code and frozen inputs

The frozen publication environment intentionally contains only run-time
dependencies. Use a separate development environment for pytest and Ruff so
installing test tools cannot change the environment used for publication runs:

```bash
python3.12 -m venv .venv-dev
.venv-dev/bin/python -m pip install -e '.[dev]'
make compile PYTHON=.venv-dev/bin/python
make test-core PYTHON=.venv-dev/bin/python
make lint PYTHON=.venv-dev/bin/python
make package PYTHON=.venv-dev/bin/python

.venv-publication/bin/python scripts/verify_publication_environment.py
make verify-inputs PYTHON=.venv-publication/bin/python
```

Important frozen inputs include:

- benchmark SHA-256:
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`
- ordered task names SHA-256:
  `fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176`
- sanitized RapidAPI fixture SHA-256:
  `eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f`
- environment lock SHA-256:
  `5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`
- fixed ToolSandbox timestamp: `1784832588`
- timezone: `America/New_York`

## Run one complete validation pair

```bash
make paper-online
```

The canonical launcher:

- requires a clean Git tree and the exact publication environment;
- starts the matched policy-wrapper control without generated tools and the
  policy-directed SAGE treatment in isolated, concurrent child processes;
- streams each uncached control row to SAGE at the matching task boundary;
- starts SAGE from an empty run-local registry;
- disables application control, response, task, and persistent output replay;
- uses the fixed clock and hash-pinned read-only external-service fixture;
- creates `dashboard/task_compare.html`, verifies the server root and served
  bytes, and opens it in the external browser before either model process;
- verifies task order, complete one-to-one coverage, process overlap, evaluator
  identity, reflection provenance, cache state, and runtime exceptions; and
- requires every saved conversation and execution context, independently
  recomputes both outcome endpoints, and reconstructs generated-tool exposure
  and calls from those raw trajectories instead of trusting result summaries.

For an online release sample, the launcher then automatically applies the
content-addressed schema-v4 sample gate. The complete audited-v9 SAGE mean must
be strictly greater than `0.80`; exactly `0.80` does not pass. This is an
adaptive technical-readiness gate for deciding whether to freeze and proceed,
not a rule for excluding outcome-low but integrity-valid campaign repetitions.

OpenAI may still report provider-managed prompt-prefix cached input tokens. That
does not replay a response or task outcome and is recorded separately.

Before a full run, the lifecycle repair mechanism can be checked with the
development-only ladder:

```bash
make lifecycle-mechanics
make lifecycle-dev10 PORT=64620
make lifecycle-dev30 PORT=64621
make lifecycle-transfer-dev30 \
  SOURCE_DEV10_RUN=outputs/lifecycle_repair/<dev10>/lifecycle_repair_diagnostic/<run> \
  PORT=64622
```

The 10- and 30-task runs deliberately seed the pinned historical faulty
abstention helper so they can prove fail, repair-or-retire, prospective canary,
and unrelated-task preservation. Their manifests and verifier mark them as
development diagnostics; they cannot qualify as publication runs.

The separate transfer target is the generalization check. It first reverifies
the exact dev10 source, then copies its complete registry and routing sidecars
into a fresh run-local directory. It runs the disjoint 30-task cohort with live
generation and lifecycle repair disabled. Verification requires byte-identical
registry state before and after, the exact promoted helper on every target
call, fresh parallel matched-control execution, and four unrelated tasks with
exact outcomes, the helper hidden, and no negative outcome delta. The ordinary
`lifecycle-dev30` target remains an independent repair-process replication; it
does not prove transfer of dev10's model-authored repair.

The development verifier also binds each observed generated-tool call to the
ordered after-task registry checkpoint and verifies that checkpoint's version
and source-code hash. This distinguishes a prospective repaired-version call
from an earlier faulty-version call in the lifecycle evidence.

To verify an already completed run:

```bash
make verify-publication \
  RUN=outputs/publication_validation/<run-stamp>/native_action
make verify-sample \
  RUN=outputs/publication_validation/<run-stamp>/native_action
```

Live calls are stochastic and hosted models can change, so a future run is not
expected to reproduce an identical trajectory. The no-regression target is the
audited outcome metric and complete integrity checks, not byte-identical model
output.

## Prepare the final ten-run campaign

Preparation writes a plan and does not make model calls:

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/publication_validation/<sample>/native_action/<run>/publication_validation_report.json \
  CAMPAIGN_ARGS='--campaign-id chapter4_policy_10x_<date> --scope online-only --expected-online-runs 10'
```

Execution remains explicitly gated:

```bash
PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py run \
  --campaign-manifest artifacts/chapter4_evidence/<campaign-id>/campaign_manifest.json \
  --wave all \
  --approve-execution
```

The publication default launches ten isolated online-build pairs concurrently;
inside every pair, the non-learning control and policy-directed SAGE processes
also run concurrently. Every pair receives a distinct preflighted dashboard
port and opens Task Compare in the external browser. The aggregate campaign
dashboard is opened externally before jobs start. Frozen-registry reuse is an
optional, explicitly requested second scope and is not part of the default
ten-pair run. Verify and analyze completed campaign artifacts with
`make verify-campaign`, `make analyze`, and `make render-paper`.

## Source layout

- `src/sage_ts/adapters/` — policy actor and ToolSandbox execution adapters
- `src/sage_ts/adequacy/` — visible-context gap classification and admission
- `src/sage_ts/generation/` — tool specifications, generation, and repair
- `src/sage_ts/validation/` — candidate validation and output normalization
- `src/sage_ts/registry/` — retained generated-tool registry
- `src/sage_ts/runtime/` — routing, injection, and execution
- `src/sage_ts/orchestration/` — online birth and lifecycle reflection
- `src/sage_ts/evaluation/` — reporting and feedback evaluators, metrics, reuse
- `scripts/run_sage_protocol.py` — paired execution protocol
- `scripts/run_native_action_4omini_ab.sh` — guarded publication launcher
- `scripts/research/` — offline campaign aggregation, not production runtime
- `tool_sandbox/` — upstream Apple benchmark code, excluded from SAGE line counts

The SAGE additions build on Apple's ToolSandbox. See `LICENSE` and
`ACKNOWLEDGEMENTS` for attribution and license terms.
