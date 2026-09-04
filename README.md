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
cleanup does not remove or simplify the deferred actor, classifier, generator,
online-birth, routing, normalization, or validation subsystems. Separate
correctness changes described below do affect outcome-only trace/lifecycle
classification, direct generated actions, and the new auto-selection arm; they
are explicit research-protocol changes rather than cleanup deletions.

## Evidence status and correction

The July ten-pair campaign is preserved as an archival development result, not
as final inferential evidence. A publication audit found that the object called
the “v140 baseline” was an expanded hybrid with 1,182 records for 1,032 tasks:
957 tasks had one record and 75 tasks had three records. The lookup averaged
compatible records for the triplicated tasks. Those hybrid values supplied the
control rows in all ten online and ten frozen arms, and the online reflection
controller also read them when making lifecycle decisions.

The outcome values previously reported for that campaign are also superseded.
They were produced before every benchmark task had an explicit,
route-independent outcome contract, and a later audit found that generic state
checks still depended on route-conditioned benchmark scoring. The independently
checked v4 rescore now uses route-independent final-state matching and each
arm's evidenced timezone. Across the preserved terminal trajectories it finds
333/1,032 exact outcomes (mean 0.4370005023280137) for the original-v140
reference and 5,981/10,320 exact outcomes across the ten SAGE replications
(mean of run means 0.6436038062482871); the lowest replication is 584/1,032
(mean 0.6276863642409402). These are historical engineering references only.
The rescore cannot repair unequal replication, online feedback, tool-birth,
routing, lifecycle, or cache provenance, so no final hypothesis decision is
claimed from the historical campaign.

The result-free Chapter 4 rerun scaffold is in
[`docs/sage_protocol/chapter4_results_completed.tex`](docs/sage_protocol/chapter4_results_completed.tex),
and the full audit is in
[`docs/sage_protocol/publication_cleanup_audit_20260901.md`](docs/sage_protocol/publication_cleanup_audit_20260901.md).
A replacement ten-pair campaign will be run only after explicit human approval.

## Corrected publication protocol

The publication launcher is
[`scripts/run_native_action_4omini_ab.sh`](scripts/run_native_action_4omini_ab.sh).
For an online publication run it enforces the following schedule and checks:

1. Start the live non-learning control and SAGE arms concurrently.
2. Require exactly one control result for each of the 1,032 ordered benchmark
   tasks.
3. Stream each same-run control row to the online reflection controller at the
   matching task boundary; SAGE waits there if its control task is still running.
4. Initialize the SAGE arm with an empty registry while the control runs in its
   own isolated child process.
5. Keep the baseline-result, SAGE-task, persistent repository whole-response,
   and persistent generated-output caches off.
6. Verify task identity, one-to-one control/candidate coverage, cache state,
   reflection provenance, and external-fixture integrity after completion.
7. Generate `dashboard/task_compare.html`, verify that the served bytes belong
   to the current run, and open it in the external/default browser before the
   first model request. Selector experiments do this for both live concurrent
   pairs: fresh control/policy SAGE and independent fresh control/auto SAGE. A
   third policy/auto causal view opens after both treatment arms complete.

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

The comparison is fail-closed and matched per task. The first live pair runs a
fresh non-learning control and policy SAGE concurrently. The policy donor captures
the exact actor-ready registry and lifecycle bytes after same-task tool birth,
plus routing decisions, generated entries, tool order, allow-list, source,
models, environment, clock, benchmark, and fixture hashes. Before each auto
task, replay restores that donor state and verifies the routed inventory before
the first model request. Independent generation, reflection, and lifecycle
mutation are disabled only in the replay arm because allowing them to run again
would create a different inventory and confound the selection comparison. Thus
the estimand is the actor-selection effect conditional on the policy donor's
exact adaptive tool-birth and lifecycle schedule. Once that authority exists,
the second live pair runs an independent fresh non-learning control and the auto
replay concurrently. That control has no path into auto's inventory or
execution; it measures the auto arm's absolute outcome behavior.

Every actor request is linked one-to-one to its model-usage record. The run
stores exact native/generated schema bundles in a content-addressed catalog and
asserts that every auto request has mode `auto`, no named `tool_choice`, and the
complete routed schema bundle. The post-run comparison reports only the frozen
outcome-evaluator values. Freshness, matching inventory, complete task coverage,
concurrency, schema/choice assertions, and runtime validity are fail-closed
experiment-integrity requirements. Generated-tool call, failure, and
unsuccessful-attempt counts remain mechanism diagnostics: they never pass or
fail the selector experiment, change its process exit, or determine full-run
pilot eligibility. The selector pilot has no predeclared policy-versus-auto
performance threshold; complete, valid policy/auto outcomes are compared and
reported without turning the noisy 30-task difference into an eligibility gate.

A generated tool may be the terminal action when it safely produces the correct
final state; the actor does not need to make a second, visible native-tool call
merely to preserve the benchmark's expected route. The underlying allow-listed
native implementation may still be used inside a validated generated tool as a
safety boundary. Final state, minefield, and runtime safety checks remain
mandatory; when a task remains unresolved or the agent abstains, the abstention
must also be correct.

Runtime recovery is also fail-closed. The one known warning-only ToolSandbox
case (`search_contacts(person_id=None)`) keeps the original actor request,
state, result, and tool trace in the same trajectory; it is not retried with a
new model sample. Genuine transient model/API retries retain the existing
bounded retry policy and now record ordered failure and trajectory-archive
provenance that the publication verifier checks before accepting either arm.

Run the sealed 30-task feasibility pilot first:

```bash
source .venv-publication/bin/activate
SAGE_RUN_STAMP=selector_pilot_$(date +%Y%m%d_%H%M%S) \
  make selector-pilot APPROVE_LIVE_RUN=YES PORT=63105
```

The pilot automatically runs the fresh-control/policy pair and then the
independent-fresh-control/auto pair. It opens the two live Task Compare views
before their model processes and the policy/auto view after both treatment arms
finish. Only after its integrity and complete-outcome checks pass **and the
researcher explicitly approves**, run one complete comparison:

```bash
source .venv-publication/bin/activate
SAGE_RUN_STAMP=selector_full_$(date +%Y%m%d_%H%M%S) \
  make selector-full \
    APPROVE_LIVE_RUN=YES \
    APPROVE_SELECTOR_FULL=YES \
    PORT=63106 \
    PILOT_EVIDENCE=/absolute/path/to/actor_selection_experiment_manifest.json
```

Each selector command starts a detached Task Compare server rooted at that
command's persistent run directory. Because that root remains bound after the
launcher exits, the pilot uses port `63105` and the full run uses `63106`; do not
reuse one port for different run roots while the earlier server is still active.

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
cache. The launcher refuses a missing or modified fixture and permits only
application mode `read_only`.

## Installation

The clean publication runtime is CPython 3.12.7 on Darwin/arm64. Its full
transitive version lock is
[`requirements-publication-lock.txt`](requirements-publication-lock.txt), with
SHA-256
`5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`.
The hash authenticates the lock file; the lock pins package versions, not wheel
artifact hashes. The 108 verified normalized external `name==version` entries
have set SHA-256
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

The compact v4 release chain is frozen in the
[`2026-09-03 release manifest`](docs/sage_protocol/publication_release_manifest_20260903.json).
`make verify-inputs` verifies the immutable
[`P0 input manifest`](docs/sage_protocol/publication_input_manifest_20260901.json),
its amendment, the active execution policy, evaluator and rescorer identities,
benchmark bytes and order, sanitized fixture,
[`historical-rescore summary`](docs/sage_protocol/historical_outcome_rescore_v4_summary.json),
[`outcome-only thresholds`](docs/sage_protocol/publication_validation_thresholds_v4.json),
and the checkpoint commit/tree. The historical summary re-evaluates preserved
terminal trajectories using independently inferred per-arm timezones; it does
not replay the campaign or repair its cache/lifecycle confounding and is not
confirmatory evidence. A history-limited shallow clone must fetch the checkpoint
ancestor before running the check.

The content-hashed checkpoint remains immutable. Its statement that generator
analysis memoization should be removed is explicitly superseded by the
[`2026-09-02 checkpoint amendment`](docs/sage_protocol/publication_checkpoint_amendment_20260902.json),
which restores the deferred within-run behavior without altering the frozen
checkpoint bytes. The extending 2026-09-03 execution policy adds concurrent-arm,
external-dashboard, direct generated-action, and outcome-only requirements.
The evaluator, rescorer, and threshold identities are content-addressed in the
validated v4 release chain.

Important frozen inputs include:

- benchmark manifest: 1,032 tasks, SHA-256
  `21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`;
- ordered task names: SHA-256
  `fec899dde5b3ce1879157c16eff120e24c1791a2ab1df53712677bcacb250176`;
- publication environment version lock: SHA-256
  `5c3ea1802331bf45809fd3e3e31fd8352473449e709cd7a443d03d1975477d1f`;
- original v140 sensitivity snapshot: 1,032 records, SHA-256
  `4f9db0f186a25a247a31fe6a934c3e87785bc80c65b455f20e677d6315638c88`;
- v4 outcome evaluator contract/source: SHA-256
  `4032411fd203ddfd061753e330cee2218d715756950b69d059792de7409efdce` /
  `c4fd84d9fbc42488c051565a96faf952c2580fca2df9e582817933aeed9e3eab`;
- historical rescorer source: SHA-256
  `17d17a2c5ca65f8a0f11d0eadb1d0a6d24a70280d1171ad0f6c722bfe214489f`;
- compact v4 rescore summary and outcome thresholds: SHA-256
  `3dc78ec78986b74230971f01b0f40bae74710de2065371c46208061d392f48a7` /
  `f14d86181b2085afc94df5c8cc39a2892f9e8c4bb44a0ba2b9d418a81d9f39f6`;
- active release manifest: SHA-256
  `8e7e2ecd4ca95e2f8484adf5610986f8d15106d6e054967940acd365c346c658`;
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
non-learning control and the matched 1,032-task SAGE arm in parallel isolated
child processes. It uses `gpt-4o-mini`, a fixed ToolSandbox clock, the pinned
read-only external fixture, an empty SAGE registry, and no experiment-result or
persistent repository whole-response caches. OpenAI's
automatic prompt-prefix computation cache remains provider-managed and is
reported separately from response reuse.

```bash
make paper-online APPROVE_LIVE_RUN=YES
```

This command is documented for the approved full validation only. It has not
been run for the current release and must not be invoked until the researcher
explicitly approves the full run.

The launcher writes to new timestamped directories beneath
`outputs/publication_validation/` and `artifacts/publication_validation/`; it
does not overwrite historical runs. It automatically invokes the publication
verifier. To verify a completed search root again:

```bash
make verify-publication \
  RUN=outputs/publication_validation/<run-stamp>/native_action
```

The frozen v4 one-sample engineering thresholds require an outcome for every
task, complete concurrent arms without
application result/response replay, zero terminal runtime failures, and the
predeclared outcome-only no-regression and same-run comparison rules. Accepted,
called, and reused tool counts remain mechanism diagnostics and cannot pass or
fail the release gate. Superseded threshold files remain tracked for audit
history. Verification requires the explicit current path:

```bash
make verify-sample \
  RUN=outputs/publication_validation/<run-stamp>/native_action \
  VALIDATION_THRESHOLDS=docs/sage_protocol/publication_validation_thresholds_v4.json
```

Passing one sample is an engineering no-regression check, not confirmatory
evidence and not a replacement for the ten-pair rerun.

Sample 01 stopped at dependency preflight before creating experiment outputs or
making model requests; its tracked ledger is
[`docs/sage_protocol/publication_validation_sample01_preflight_20260901.json`](docs/sage_protocol/publication_validation_sample01_preflight_20260901.json).
Sample 02 was the first completed strict-intent attempt. It completed both
1,032-task arms, but it predates the target route-independent evaluator and concurrent-arm
protocol and is **configuration-ineligible**. Its old values must not be used as
current outcome results. The diagnostic record is
[`docs/sage_protocol/publication_validation_sample02_report.md`](docs/sage_protocol/publication_validation_sample02_report.md).
That post-run audit also found and corrected two release drifts: removed
within-run generator memoization and an omitted historical five-retry setting.
The replacement launcher now fail-closes all retry layers and request timeouts.
It also rejects diagnostic force/exposure variables in either publication arm.

Sample 03 completed an earlier engineering validation, but it used a partial
outcome-evaluator surface and predates the current concurrent-pair requirement.
It is an archival diagnostic only; none of its values is a current result,
threshold, or release claim.

The September 2 ten-online/ten-frozen campaign manifest is also superseded and
was never executed. A new manifest will be prepared only from a passing sample
under the frozen v4 evaluator, concurrent-arm launcher, and dashboard policy.
Preparation makes no model calls; execution still requires separate, explicit
researcher approval.

To evaluate an already-built registry under the same fresh-control protocol:

```bash
RESUME_REGISTRY_CHECKPOINT=artifacts/<registry> \
  make paper-frozen APPROVE_LIVE_RUN=YES
```

## Final paper rerun (not started)

Preparation is deliberately separate from execution. After the researcher
approves and the current full validation sample passes, prepare a new manifest
with that report:

```bash
make prepare-paper-rerun \
  SAMPLE_REPORT=outputs/publication_validation/<current-run>/native_action/<protocol-run>/publication_validation_report.json \
  CAMPAIGN_ARGS='--campaign-id chapter4_strict_fresh_control_10x_<date> --expected-online-runs 10'
```

The manifest will pin the passing single-sample report, validated Git
commit/tree, evaluator, runtime and generation digests, benchmark, fixture, and
exactly ten online/frozen pairs. There is no active current-release campaign
manifest yet, and no full current-release model run has started.

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
