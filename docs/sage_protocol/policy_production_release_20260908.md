# Policy-Directed SAGE Production Release

Date: 2026-09-08

Branch: `codex/paper-policy-production-final`

## Release decision

This branch restores the policy-directed SAGE configuration associated with the
large ToolSandbox outcomes reported in the paper. It does not claim natural
base-model selection of generated tools or causal isolation of any one retained
component. The policy controller's instructions, schema filtering,
deterministic selector cascade, and named `tool_choice` requests are part of the
intervention and must be disclosed as such.

## Historical provenance

All ten archived online runs report commit
`25466400ae48b4520a3d7cf914d9c85d3a512755` plus local changes. The recorded
source-tree hashes are:

- replications 1--5:
  `d6aad9bc350a3e6ba7389298d7ed66deaacdff54064fa4f4db5c15fd1463a928`
- replications 6--10:
  `39214520a16a8d3273c8b91f3d0c41163d33d9ae6cd538839a2c31715ceb07bd`

The local patches that produced either hash were not preserved. An exact
byte-for-byte restoration is therefore impossible from Git history. The clean
algorithm donor is commit
`5bf1a1a3377bb913cb11fdcd1228f18003300714`, tree
`718ef02a85f0490d7e4dbbec4192567a1bd10b9d`. Its complete validation produced a
paper-era-evaluator SAGE outcome of `0.7900`, inside the archived ten-run range
`0.7761--0.8095`.

## Result-critical mechanism

The retained mechanism comprises:

1. visible-context inadequacy classification and candidate admission;
2. online tool birth, model-authored generation, and repair;
3. schema, AST, sandbox, held-out, and negative-applicability validation;
4. registry storage, lifecycle reflection, and task-conditioned routing;
5. native/generated ToolSandbox injection and execution;
6. policy-directed actor instructions, schema filtering, selector cascade, and
   named tool choices;
7. output normalization and reuse accounting; and
8. separate behavioral-feedback and reporting outcome evaluators.

Fourteen of the twenty lift-producing mechanism files are byte-identical to the
clean donor. The six changed mechanism files are the actor, classifier,
generator, lifecycle reflection, output-normalization, and online-feedback
evaluator modules. Their post-donor changes include restored policy behavior,
fresh same-task control feedback, evaluator identity and feedback handling, and
the audited repairs documented in this branch. Online birth, routing,
ToolSandbox integration, and validation remain byte-identical to the donor.

## Measurement and protocol corrections

The paper-era evaluator remains internal because it affected tool birth and
lifecycle decisions. The 2026-09-10 measurement amendment uses two explicit
outcome scopes: audited v9 on all 1,032 tasks for current same-run lift, and the
unchanged paper-v1 evaluator on the exact ordered 800-task subset for historical
paper comparisons. Lifecycle feedback uses paper-v1 when available and audited
v9 as the fallback on the other 232 tasks. Canonical similarity is descriptive
only and is never a release or paper-result gate.

Lifecycle feedback is a post-task scalar computed by evaluators from benchmark
answer/state contracts. The actor and generated tools do not receive raw
expected answers, target state, or evaluator traces during the task. This is a
reward-feedback-driven system and must not be described as globally label-free.

The July campaign also used a strict hybrid control cache for both comparison
rows and online reflection. That condition is preserved in source for archival
replay, but it is prohibited by the canonical new-run launcher. New publication
runs use fresh concurrent control/SAGE processes, stream one matching control
row at each task boundary, and fail closed on cache use, missing coverage,
runtime exceptions, source drift, wrong environment imports, or a dashboard
that was not externally opened before either model process.

## Cleanup boundary

Cleanup removes 13,401 physical lines across 40 disconnected files: obsolete
analysis/reporting utilities, registry/cohort migrations, cache-accounting
scripts, superseded dashboard patch servers, legacy launchers, four tests tied
only to removed utilities, and stale figure generators that encoded the
withdrawn natural-selection claim.

No whole non-dashboard `sage_ts` implementation module is safely removable:
static entry-point reachability shows every such module is used by the guarded
runner. Behavioral reductions inside the actor, classifier, generator,
online-birth, routing, normalization, validation, or lifecycle code are
deliberately deferred.

## Physical line counts

Counts use `wc -l`, include comments and blank lines, and exclude all dashboard
code/templates and all native `tool_sandbox` code.

- lift-producing scientific mechanism: **33,231** lines;
- installed non-dashboard `sage_ts` package: **45,373** lines;
- runnable and verified single-pair production surface (package plus canonical
  runner, launcher, and three publication verifiers): **51,227** lines; and
- executable ten-pair campaign surface, adding the campaign runner, sample
  verifier, and evidence aggregator: **58,066** lines before optional paper
  rendering/bootstrap utilities.

The earlier `32,260` figure was a narrower natural-selection-branch manifest,
not a total production-application count. It also omitted behavior-changing
feedback/strata code and the audited reporting evaluator, so it must not be
reported as total SAGE.

## Completed execution gate

The clean publication tree completed ten online-build and ten paired
frozen-registry runs with fresh controls, full 1,032-task coverage, zero runtime
exceptions, and passing v3 dual-endpoint campaign-inclusion gates. Audited v9
online outcome was `0.586176 -> 0.783543`; the exact paper-comparable v1 subset
was `0.497535 -> 0.800336`. The selected cohort uses integrity-only technical
replacements for online replication 4 and frozen replication 5 while preserving
both failed originals. Final values, replacement disclosures, and artifact
hashes are recorded in
[`policy_production_final_evidence_20260916.md`](policy_production_final_evidence_20260916.md).
