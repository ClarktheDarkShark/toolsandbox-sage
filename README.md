# SAGE ToolSandbox

SAGE is a research implementation of self-evolving tool use on the complete
1,032-task ToolSandbox benchmark. During an online run, SAGE identifies repeated
capability gaps, generates deterministic Python tools, validates and repairs
them, retains accepted tools in a registry, and makes them available to later
tasks. The repository contains the benchmark integration, online lifecycle,
registry, evaluation, dashboard, and publication-evidence pipeline used by the
paper.

This release is intentionally narrower than the development repository. The
post-campaign custom-task product, CyberGym adapter, and promotion-only or
test-only runtime paths are not part of the publication implementation. The
actor, classifier, generator, online-birth, routing, normalization, and
validation behavior used by the study has not been simplified as part of this
cleanup. The narrow provenance changes described below are the only exceptions.

## Evidence status and correction

The July ten-pair campaign is preserved as an archival development result, not
as final inferential evidence. A publication audit found that the object called
the “v140 baseline” was an expanded hybrid with 1,182 records for 1,032 tasks:
957 tasks had one record and 75 tasks had three records. The lookup averaged
compatible records for the triplicated tasks. Those hybrid values supplied the
control rows in all ten online and ten frozen arms, and the online reflection
controller also read them when making lifecycle decisions.

A sensitivity calculation shows why this is a provenance and intervention
problem rather than evidence that the reported headline was inflated. The
hybrid outcome mean was 0.457342; the original one-record-per-task v140 outcome
mean was 0.452803. Holding the historical SAGE mean of 0.795407 fixed changes
the relative point estimate from approximately 73.9% to 75.7%. That calculation
does not repair unequal replication, confidence intervals, randomization
tests, mechanism attribution, or cache-conditioned online decisions. No final
hypothesis decision is claimed from the historical campaign.

The corrected Chapter 4 text is in
[`docs/sage_protocol/chapter4_results_completed.tex`](docs/sage_protocol/chapter4_results_completed.tex),
and the full audit is in
[`docs/sage_protocol/publication_cleanup_audit_20260901.md`](docs/sage_protocol/publication_cleanup_audit_20260901.md).
A replacement ten-pair campaign will be run only after explicit human approval.

## Corrected publication protocol

The canonical launcher is
[`scripts/run_native_action_4omini_ab.sh`](scripts/run_native_action_4omini_ab.sh).
For an online publication run it enforces the following sequence and checks:

1. Run the complete live control arm first.
2. Require exactly one control result for each of the 1,032 ordered benchmark
   tasks.
3. Supply those same-run control rows to the online reflection controller.
4. Run the SAGE arm from an empty registry.
5. Keep the baseline-result, SAGE-task, persistent repository whole-response,
   and persistent generated-output caches off.
6. Verify task identity, one-to-one control/candidate coverage, cache state,
   reflection provenance, and external-fixture integrity after completion.

Strict mode does not construct or read the historical control baseline cache.
Ambiguous duplicate entries in the legacy cache reader fail closed rather than
being averaged.

One narrow strict-mode exclusion prevents other runs' history from entering a
strict run. Strict publication runs disable cross-run failure-memory input;
nonpublication runs retain that development behavior. The generator's validated
within-run contract-and-repair-analysis memoization remains unchanged: it can reuse an
identical public-contract or rejected-code repair analysis during one generator
lifetime, but it is never persisted or loaded from another run. The launcher
additionally requires a clean Git tree
and the exact validated isolated Python environment before it can start either
arm.

### Matched actor-selection arm

The actor exposes an explicit `actor_selection_mode=policy|auto` setting. The
default `policy` mode is the publication implementation: selector prompting,
the selection cascade, dynamic generated-schema filtering, wrapped-native
schema hiding, and any named `tool_choice` remain active. The experimental
`auto` mode takes the first branch in actor inference and sends the original
conversation plus every routed native and generated schema directly to the
upstream model. It does not run any of those policy-selection interventions.

The comparison is fail-closed and matched per task. A policy donor run captures
the exact actor-ready registry and lifecycle bytes after same-task tool birth,
plus routing decisions, generated entries, tool order, allow-list, source,
models, environment, clock, benchmark, and fixture hashes. Before each auto
task, replay restores that donor state and verifies the routed inventory before
the first model request. Independent generation, reflection, and lifecycle
mutation are disabled only in the replay arm because allowing them to run again
would create a different inventory and confound the selection comparison. Thus
the estimand is the actor-selection effect conditional on the policy donor's
exact adaptive tool-birth and lifecycle schedule.

Every actor request is linked one-to-one to its model-usage record. The run
stores exact native/generated schema bundles in a content-addressed catalog and
asserts that every auto request has mode `auto`, no named `tool_choice`, and the
complete routed schema bundle. The post-run comparison excludes canonical
similarity and reports only outcome-evaluator values. It also rejects response
cache hits, task/order drift, schema drift, terminal runtime exceptions, and
incomplete generated-tool attempts. The pilot additionally requires zero
generated-tool execution failures before the full comparison is allowed; the
full comparison records those failures as outcome-relevant behavior instead of
silently discarding the arm.

Run the sealed 30-task feasibility pilot first:

```bash
source .venv-publication/bin/activate
SAGE_RUN_STAMP=selector_pilot_$(date +%Y%m%d_%H%M%S) \
  ./scripts/run_native_action_4omini_ab.sh pilot 63105 native-only
```

The pilot automatically runs a fresh control, policy donor, and matched auto
arm. Only after its stability gate passes, run one 1,032-task comparison:

```bash
source .venv-publication/bin/activate
SAGE_AUTO_SELECTION_EXPERIMENT=1 \
SAGE_AUTO_SELECTION_PILOT_EVIDENCE=/absolute/path/to/actor_selection_experiment_manifest.json \
SAGE_RUN_STAMP=selector_full_$(date +%Y%m%d_%H%M%S) \
  ./scripts/run_native_action_4omini_ab.sh full 63105 native-only
```

The normal `full` command remains the original two-arm protocol unless
`SAGE_AUTO_SELECTION_EXPERIMENT=1` is set. Selector runs add
`actor_selection_outcome_comparison.json` and
`actor_selection_experiment_manifest.json` to the protocol run root, alongside
the policy `candidate/` and `sage_auto_selection/` run directories.
The full selector launcher re-verifies the supplied pilot manifest and all of
its sealed artifacts before making any new model request.

“Fresh model call” here means that SAGE does not replay a stored model response.
OpenAI separately enables provider-managed prompt-prefix caching for supported
models. GPT-4o Mini can therefore report cached input tokens even though it
generates a new response for every call. Strict runs record those tokens
separately and never describe them as SAGE response-cache hits. The publication
verifier requires provider-prefix metadata for every model call and reconciles
the raw call events exactly with each task row and arm summary; missing or
partial accounting fails closed. See the
[OpenAI prompt-caching documentation](https://developers.openai.com/api/docs/guides/prompt-caching).

ToolSandbox tasks that query weather, stocks, location search, or currency use
the frozen, sanitized fixture at
[`artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json`](artifacts/publication_cleanup_20260901/fixtures/rapid_api_cache.sanitized.json).
It contains 85 deterministic external-service responses, no credentials, and
has SHA-256
`eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f`.
The fixture is a read-only benchmark input that replaces unstable network
responses; it is not a model, task, prompt, control, or experiment-result
cache. The launcher refuses a missing, modified, or writable-mode fixture.

## Installation

The clean publication runtime is CPython 3.12.7 on Darwin/arm64. Its full
transitive version lock is
[`requirements-publication-lock.txt`](requirements-publication-lock.txt), with
SHA-256
`5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`.
The hash authenticates the lock file; the lock pins package versions, not wheel
artifact hashes. The 108 verified external `name==version` entries have
canonical set SHA-256
`006191cd1efca9e244c6b5d6fb6a8c91fb95c279959cc91c9eada316f904fc9d`.
This dependency-valid isolated lock defines the new release runtime. It is not
claimed to reconstruct the July campaign environment, which was not captured,
or the later 533-package cleanup-host snapshot preserved in the local recovery
bundle.

Create or refresh the isolated runtime, then activate it:

```bash
./scripts/bootstrap_env.sh .venv-publication
source .venv-publication/bin/activate
python scripts/verify_publication_environment.py
```

The bootstrap requires `python3.12` to report exactly 3.12.7, installs the full
lock, installs only this checkout as an editable package without resolving new
dependencies, runs `pip check`, and runs the strict environment verifier. The
verifier rejects a non-virtual environment, a different OS/architecture, any
missing or mismatched locked distribution, and every unexpected external
distribution.

The package metadata supports Python 3.11 and 3.12 for general development.
Developer tools belong in a separate environment and are intentionally rejected
by the strict launcher:

```bash
conda env create -f environment.yml
conda activate toolsandbox-sage-dev
```

Set `OPENAI_API_KEY` in the environment before a live run. A local
`.secrets/env.sh` may be used by the launcher, but secrets must never be
committed.

## Validation and packaging

Compile the retained Python surface and run the critical publication tests:

```bash
make compile
make test-core
```

The complete local unit/integration suite, lint checks, and distribution build
are separate targets:

```bash
make test
make lint
make package
```

The wheel includes the Chapter 4 dashboard HTML and the ToolSandbox role YAML
used at runtime.

The compact publication inputs shipped in Git can be checked from a clean clone
without running an experiment or obtaining private/local archives:

```bash
make verify-inputs
```

The verifier reads the tracked release chain at
[`docs/sage_protocol/publication_release_manifest_20260902.json`](docs/sage_protocol/publication_release_manifest_20260902.json).
That chain content-addresses all three active policy documents: the immutable
[`P0 input manifest`](docs/sage_protocol/publication_input_manifest_20260901.json)
and its policy amendment, plus the active outcome-only validation thresholds.
It verifies the benchmark bytes, count, and ordered task names; the sanitized
external-service fixture and its credential-safety invariants; the tracked
historical analysis references; the validation thresholds; and resolution of
the checkpoint commit to its recorded Git tree. A history-limited shallow clone
must fetch the checkpoint ancestor before running this check.

The content-hashed checkpoint remains immutable. Its statement that generator
analysis memoization should be removed is explicitly superseded by the
[`2026-09-02 checkpoint amendment`](docs/sage_protocol/publication_checkpoint_amendment_20260902.json),
which restores the deferred within-run behavior and records the complete pinned
execution and outcome-only validation policies without altering the frozen
checkpoint bytes.

Important frozen inputs include:

- benchmark manifest: 1,032 tasks, SHA-256
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`;
- ordered task names: SHA-256
  `fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176`;
- publication environment version lock: SHA-256
  `5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`;
- original v140 sensitivity snapshot: 1,032 records, SHA-256
  `4f9db0f186a25a247a31fe6a934c3e87785bc80c65b455f20e677d6315638c88`;
- authoritative local publication manifest: SHA-256
  `9a7c53fb9c305279dd2eedf5bf5af93e98c37f91b71d028eb065524ec381a8b2`.

The v140 snapshot is a historical sensitivity reference only. It is explicitly
ineligible as a control source for new experiments.

The full 23 MB recovery bundle remains a local, immutable audit artifact because
it contains the pre-cleanup source archive, including code deliberately removed
from the publication product. GitHub carries the compact hash index, checkpoint
commit/tree, public benchmark, sanitized fixture, historical analysis
references, and validation thresholds. If the full ignored recovery bundle is
present on the cleanup host, `make verify-freeze` performs the optional deeper
local audit; it is not required for clean-clone reproduction.

## Run one complete fresh-control sample

The following starts one complete online-build sample: a fresh 1,032-task
control followed by the matched 1,032-task SAGE arm. It uses `gpt-4o-mini`, a
fixed ToolSandbox clock, the pinned read-only external fixture, an empty SAGE
registry, and no experiment-result or persistent repository whole-response
caches. OpenAI's
automatic prompt-prefix computation cache remains provider-managed and is
reported separately from response reuse.

```bash
make paper-online
```

The launcher writes to new timestamped directories beneath
`outputs/publication_validation/` and `artifacts/publication_validation/`; it
does not overwrite historical runs. It automatically invokes the publication
verifier. To verify a completed search root again:

```bash
make verify-publication \
  RUN=outputs/publication_validation/<run-stamp>/native_action
```

The active one-sample engineering gate is separately frozen in
[`docs/sage_protocol/publication_validation_thresholds_v2.json`](docs/sage_protocol/publication_validation_thresholds_v2.json).
It requires complete arms without application result/response replay, zero
runtime exceptions, the historical ten-run lower envelope for candidate
outcome, at least 10% outcome lift over the new same-run control, and observed
accepted/called/reused generated tools. Outcome/task-completion similarity is
the sole performance endpoint. Canonical/reference similarity is descriptive
only and can never fail this gate. The superseded v1 threshold remains tracked
for audit history. The active
`persistent_generation_output_replay_enabled=false` threshold names the retired
persistent generated-output cache, not the within-run generator memoization or
OpenAI's provider prefix cache. The integrity gate also requires complete per-call
provider-prefix metadata and exact event/task/arm reconciliation. The gate reports
comparison with the historical mean but never reruns or selects a better sample:

```bash
make verify-sample \
  RUN=outputs/publication_validation/<run-stamp>/native_action
```

Passing one sample is an engineering no-regression check, not confirmatory
evidence and not a replacement for the ten-pair rerun.

Sample 01 stopped at dependency preflight before creating experiment outputs or
making model requests; its tracked ledger is
[`docs/sage_protocol/publication_validation_sample01_preflight_20260901.json`](docs/sage_protocol/publication_validation_sample01_preflight_20260901.json).
Sample 02 was the first completed strict-intent attempt. It completed both
1,032-task arms with zero runtime
exceptions, zero cached control tasks, zero persistently replayed whole model
responses, and exact same-run reflection mapping. Its candidate outcome score
(`0.7788122917`) passed the historical lower-envelope gate
(`0.7760515297`), and its relative outcome lift was `58.04%`. The initial v1
report incorrectly treated canonical/reference similarity as a release gate;
that policy is now explicitly superseded and content-addressed. Sample 02 is
still **configuration-ineligible**. The diagnostic record is
[`docs/sage_protocol/publication_validation_sample02_report.md`](docs/sage_protocol/publication_validation_sample02_report.md).
That post-run audit also found and corrected two release drifts: removed
within-run generator memoization and an omitted historical five-retry setting.
The replacement launcher now fail-closes all retry layers and request timeouts.
It also rejects diagnostic force/exposure variables in either publication arm.

Sample 03 is the completed corrected-tree engineering validation. Both arms
completed all 1,032 tasks with zero runtime exceptions, zero cached control
tasks, zero repository whole-response replay, and same-run-fresh reflection.
Across the 800 tasks with an outcome evaluator, outcome increased from
`0.5087366331780064` to `0.7986035515693737`: an absolute increase of
`0.2898669183913673` and a relative lift of `56.97779548144769%`. Exact
outcome successes increased from `220` to `443`; paired outcomes comprised
`413` gains, `283` preserved results, and `104` regressions. The outcome-only
sample verifier passed. The tracked record is
[`docs/sage_protocol/publication_validation_sample03_report.md`](docs/sage_protocol/publication_validation_sample03_report.md).

The ten-online/ten-frozen manifest has been prepared and verified at
`artifacts/chapter4_evidence/chapter4_strict_fresh_control_10x_20260902/campaign_manifest.json`.
Its initial SHA-256 is
`af5045911ac96e2bfdd67fac5aed3ce5b22cae6389ca94832d340b6d719d4853`.
The ten online and ten matched frozen runs are queued but unstarted.
Preparation made no model calls. The campaign has **not** been executed and
still requires explicit researcher approval. Execution is pinned to validated
runtime commit `519d6fa3739f4c933487073c5888f7576e2a646a` and tree
`718ef02a85f0490d7e4dbbec4192567a1bd10b9d`, not the later
documentation-only commit. The clean public-history runtime checkpoint is
`5bf1a1a3377bb913cb11fdcd1228f18003300714`; it has that identical validated
tree while omitting intermediate commits that contained removed experiments.

To evaluate an already-built registry under the same fresh-control protocol:

```bash
RESUME_REGISTRY_CHECKPOINT=artifacts/<registry> make paper-frozen
```

## Prepared final paper rerun

Preparation is deliberately separate from execution. The active manifest was
created with the following command; preparation did not make model calls:

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/publication_validation/publication_validation_20260902_strict_sample03/native_action/online_build_full_20260902_071820/publication_validation_report.json \
  CAMPAIGN_ARGS='--campaign-id chapter4_strict_fresh_control_10x_20260902 --expected-online-runs 10'
```

The prepared manifest pins the passing single-sample report, validated Git
commit/tree, runtime and generation digests, benchmark, fixture, and exactly
ten online/frozen pairs. This later documentation update does not change the
pinned runtime identity.

After explicit approval, the guarded campaign runner requires both the
prepared manifest and `--approve-execution`:

```bash
PYTHONPATH=src:. python scripts/run_chapter4_evidence_campaign.py run \
  --campaign-manifest artifacts/chapter4_evidence/<campaign-id>/campaign_manifest.json \
  --wave all \
  --approve-execution
```

Do not run that command merely to prepare or inspect the campaign. Completed
campaign outputs can be verified and analyzed with explicit paths:

```bash
make verify-campaign \
  CAMPAIGN_MANIFEST=artifacts/chapter4_evidence/<campaign-id>/campaign_manifest.json

make analyze \
  CAMPAIGN_MANIFEST=artifacts/chapter4_evidence/<campaign-id>/campaign_manifest.json \
  ANALYSIS_OUTPUT=artifacts/chapter4_evidence/<campaign-id>/analysis

make render-paper \
  EVIDENCE_DATA=artifacts/chapter4_evidence/<campaign-id>/analysis/chapter4_evidence_data.json \
  TABLE_OUTPUT=artifacts/chapter4_evidence/<campaign-id>/tables
```

Analysis is generated from the versioned campaign manifest and raw run
artifacts. The renderer requires an explicit evidence-data file and output
directory; it does not contain hard-coded result values.

## Retained implementation

- `scripts/run_sage_protocol.py`: paired ToolSandbox control/SAGE protocol.
- `src/sage_ts/adapters/`: ToolSandbox and OpenAI adapters.
- `src/sage_ts/adequacy/`: gap classification and candidate gates.
- `src/sage_ts/generation/`: tool specification and generation.
- `src/sage_ts/validation/`: AST, schema, sandbox, live, and output checks.
- `src/sage_ts/registry/`: accepted-tool registry.
- `src/sage_ts/runtime/`: ToolSandbox injection, base-tool policy, and routing.
- `src/sage_ts/orchestration/`: online birth and fresh-control reflection.
- `src/sage_ts/evaluation/`: outcome, lifecycle, usage, and Chapter 4 evidence.
- `src/sage_ts/dashboard/`: run and publication evidence views.
- `tool_sandbox/`: the upstream benchmark environment, scenarios, roles,
  tools, and scoring code.

The SAGE additions build on Apple's ToolSandbox. See `LICENSE` and
`ACKNOWLEDGEMENTS` for license terms and upstream attribution.

## Reproducibility limits

Live `gpt-4o-mini` calls are stochastic and the hosted model can change, so
future runs are not expected to be bit-for-bit identical. The historical July
campaign did not capture its exact dirty trees, package environment, or
external fixture hash. The cleanup checkpoint and current publication inputs
are now content-hashed, but those records cannot retroactively supply missing
historical provenance. Final statistical claims therefore await the approved
fresh-control campaign from one clean release state.
