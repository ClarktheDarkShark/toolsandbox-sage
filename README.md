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
distributional behavioral equivalence on the historical measurement; it is not
presented as an audited-v5 outcome. New runs report v5 outcomes, whose corrected
coverage and contracts make their numerical scale non-interchangeable with the
paper values.

The accurate description for this release is therefore:

> Clean, behavior-equivalent reconstruction of the policy-directed paper
> runtime, with separately audited measurement and fail-closed run provenance.

The detailed historical audit is in
[`docs/sage_protocol/publication_cleanup_audit_20260901.md`](docs/sage_protocol/publication_cleanup_audit_20260901.md).
The final restoration boundary, mechanism inventory, and reproducible line
counts are recorded in
[`docs/sage_protocol/policy_production_release_20260908.md`](docs/sage_protocol/policy_production_release_20260908.md).

## Why the paper system succeeded

The principal lift mechanism was an external actor policy, not natural model
selection. On each actor request the policy can:

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
not restore the validated algorithm. This release therefore separates the two
roles:

- `outcome_similarity` is computed by the audited v5 evaluator and is the only
  reported performance endpoint;
- `online_feedback_outcome_similarity` is computed by the paper-era evaluator
  and is used only inside the restored classifier/lifecycle feedback loop.

Both evaluator identities are written to every run manifest. The compatibility
signal is never presented as the final outcome result. This split preserves the
studied policy behavior without recovering favorable paper numbers through a
known measurement defect.

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

```bash
make compile
make test-core
make package
make verify-inputs
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
- starts the non-learning control and policy-directed SAGE in isolated,
  concurrent child processes;
- streams each uncached control row to SAGE at the matching task boundary;
- starts SAGE from an empty run-local registry;
- disables application control, response, task, and persistent output replay;
- uses the fixed clock and hash-pinned read-only external-service fixture;
- creates `dashboard/task_compare.html`, verifies the server root and served
  bytes, and opens it in the external browser before either model process; and
- verifies task order, complete one-to-one coverage, process overlap, evaluator
  identity, reflection provenance, cache state, and runtime exceptions.

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

## Prepare the final ten-run campaign

Preparation writes a plan and does not make model calls:

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/publication_validation/<sample>/native_action/<run>/publication_validation_report.json \
  CAMPAIGN_ARGS='--campaign-id chapter4_policy_10x_<date> --expected-online-runs 10'
```

Execution remains explicitly gated:

```bash
PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py run \
  --campaign-manifest artifacts/chapter4_evidence/<campaign-id>/campaign_manifest.json \
  --wave all \
  --approve-execution
```

Use a distinct dashboard port for every concurrently launched pair. Verify and
analyze completed campaign artifacts with `make verify-campaign`, `make analyze`,
and `make render-paper`.

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
