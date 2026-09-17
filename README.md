# SAGE for ToolSandbox

This repository contains the production research implementation of SAGE used
with Apple's 1,032-task ToolSandbox benchmark. SAGE detects recurring capability
gaps, generates and validates reusable Python tools, retains accepted tools in a
registry, routes them to later tasks, and applies an actor policy that selects and
sequences the generated and native tools.

This release intentionally restores the **policy-directed** SAGE studied in the
paper. It does not claim that the base model naturally chooses generated tools.
The later natural-selection experiments are not part of this branch.

## Publication release and evidence

The publication runtime is pinned to commit
`4ce1c6de0ab36dd59e1a319f4e56e298133f4a79` and tree
`4640019c7a054d4af6a500e7327ebbd0a507bfc5`. Every selected run records that
exact clean identity, the same locked environment, benchmark order, frozen
clock, evaluator hashes, and read-only external-service fixture.

The completed evidence cohort contains ten online-build runs and ten paired
frozen-registry runs. Each run includes all 1,032 tasks, a fresh matched
control, no application-level response or result cache, and zero runtime
exceptions. Two original executions failed the zero-exception integrity gate
and remain preserved: online `rep04` and frozen `rep05`. They were replaced by
`rep04r1` and `rep05r1`, respectively. Replacement eligibility depended only
on the predeclared integrity gate, never on observed performance.

Across the ten online-build runs, audited v9 outcome was `0.586176` for the
matched control and `0.783543` for SAGE, an absolute difference of `+0.197368`
and relative lift of `+33.67%`. On the exact paper-comparable 800-task v1
subset, the means were `0.497535` and `0.800336`; SAGE ranged from `0.784749`
to `0.814361`. The ten frozen-registry runs produced a v9 SAGE mean of
`0.776195` and retained `96.28%` of the online-build gain.

The selected cohort, replacement disclosures, endpoint identities, hashes,
and paper-ready values are recorded in
[`docs/sage_protocol/policy_production_final_evidence_20260916.md`](docs/sage_protocol/policy_production_final_evidence_20260916.md).

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

The other critical components are:

- visible-context inadequacy classification and candidate admission;
- online tool birth, model-authored generation, and repair;
- schema, AST, sandbox, held-out, and negative-applicability validation;
- registry storage, lifecycle reflection, and task-conditioned routing;
- native/generated ToolSandbox injection and execution;
- output normalization, reuse accounting, and outcome evaluation.

These mechanisms remain intact. Cleanup removed obsolete reporting, cohort,
registry-migration, cache-accounting, and dashboard patch utilities that are not
reachable from the production runner. Chapter 4 aggregation remains available
under `scripts/research/`, outside the installed `sage_ts` package.

## Outcome measurement and behavioral compatibility

The paper-era outcome evaluator influenced online tool birth and lifecycle
decisions. Replacing it in place would change later registry contents and would
not restore the validated algorithm. This release therefore keeps the feedback
and reporting roles distinct:

- `outcome_similarity` is computed by audited v9 for all 1,032 tasks. It is the
  current same-run outcome endpoint and supplies the control-to-SAGE lift gate;
- `online_feedback_outcome_similarity` is computed by paper-era v1 on its exact
  ordered 800-task applicability subset. It is the only endpoint compared with
  the historical paper range and is also the preferred lifecycle feedback
  signal on those tasks; and
- on the other 232 tasks, lifecycle feedback falls back to the audited v9
  outcome. Canonical score deltas can inform internal lifecycle decisions but
  are never a release or paper-result gate.

These are post-task, evaluator-derived scalar feedback signals. Benchmark
answer and state targets are used by the evaluators, but raw targets, expected
answers, and evaluator traces are not provided to the actor or generated tools
before or during that task. Both evaluator identities and hashes are written to
the run artifacts. This split preserves the studied policy behavior without
comparing incompatible task sets or evaluator versions.

The completed ten-run online cohort is the primary current result. Audited v9
uses all 10,320 matched task observations and paper-comparable v1 uses 8,000.
The v1 SAGE mean of `0.800336` is above the archived paper mean of `0.795407`.
Endpoint values are never mixed: v9 supports current same-run inference, while
v1 is used only for the apples-to-apples historical comparison.

## Historical cache limitation

The successful July campaign used a strict hybrid control cache, and those
cached rows also informed online reflection. The cache contained 1,182 records
for 1,032 tasks, including 75 triplicated tasks. Consequently, the archived ten
runs are evidence of the policy system under that cache-conditioned protocol,
not clean fresh-control causal evidence.

The legacy cache reader remains in the source only to preserve historical
behavior and artifact compatibility. It is ineligible for new publication
runs. All 20 selected publication runs used fresh controls and recorded zero
cached task, control, or response reuse.

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
- starts the matched control and policy-directed SAGE in isolated,
  concurrent child processes;
- streams each uncached control row to SAGE at the matching task boundary;
- starts SAGE from an empty run-local registry;
- disables application control, response, task, and persistent output replay;
- uses the fixed clock and hash-pinned read-only external-service fixture;
- creates `dashboard/task_compare.html`, verifies the server root and served
  bytes, and opens it in the external browser before either model process; and
- verifies task order, complete one-to-one coverage, process overlap, evaluator
  identity, reflection provenance, cache state, and runtime exceptions.

The matched control is not the stock ToolSandbox agent. It uses the same model
settings, task order, execution harness, and configurable policy-aware actor
wrapper as SAGE, but it has no generated-tool registry, cannot generate or
learn tools, and receives only the native ToolSandbox inventory. This isolates
the contribution of the SAGE tool system within the studied production setup.

OpenAI may still report provider-managed prompt-prefix cached input tokens. That
does not replay a response or task outcome and is recorded separately.

To verify an already completed run:

```bash
make verify-publication \
  RUN=outputs/publication_validation/<run-stamp>/native_action
```

Live calls are stochastic and hosted models can change, so a future run is not
expected to reproduce an identical trajectory. The no-regression target is the
audited outcome metric and complete integrity checks, not byte-identical model
output.

## Reproduce the completed ten-run campaign

Preparation writes a plan and does not make model calls:

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/publication_validation/<sample>/native_action/<run>/publication_validation_report.json \
  CAMPAIGN_ARGS='--campaign-id chapter4_policy_10x_<date> --scope online-and-frozen --expected-online-runs 10'
```

Execution remains explicitly gated:

```bash
PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py run \
  --campaign-manifest artifacts/chapter4_evidence/<campaign-id>/campaign_manifest.json \
  --wave all \
  --approve-execution
```

The runner launches ten isolated online-build pairs concurrently; inside every
pair, the matched control and policy-directed SAGE processes also run
concurrently. Every pair receives a distinct preflighted dashboard port and
opens Task Compare in the external browser. With `online-and-frozen`, the
second wave evaluates each independently learned registry with generation and
repair disabled. Verify and analyze completed campaign artifacts with
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
