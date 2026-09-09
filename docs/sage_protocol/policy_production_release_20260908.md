# Policy-Directed SAGE Production Release

Date: 2026-09-08

Branch: `codex/paper-policy-production`

## Release decision

This branch restores the policy-directed SAGE intervention responsible for the
large ToolSandbox outcomes reported in the paper. It does not claim natural
base-model selection of generated tools. The policy controller's instructions,
schema filtering, deterministic selector cascade, and named `tool_choice`
requests are part of the intervention and must be disclosed as such.

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

Eighteen of the twenty lift-producing mechanism files are byte-identical to the
clean donor. `online_feedback_score.py` is the donor evaluator plus a two-line
identity tag. `self_evolution_reflection.py` adds the fresh same-task control
stream and reads that explicit compatibility signal. The actor, classifier,
generator, online-birth, routing, ToolSandbox integration, normalization, and
validation implementations remain byte-identical to the donor.

## Measurement and protocol corrections

The paper-era evaluator remains internal because it affected tool birth and
lifecycle decisions. The audited v5 evaluator is used for reported outcomes.
This preserves the reconstructed algorithm while preventing known evaluator
false negatives from being published as final results.

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

- lift-producing scientific mechanism: **32,955** lines;
- installed non-dashboard `sage_ts` package: **43,851** lines;
- runnable and verified single-pair production surface (package plus canonical
  runner, launcher, and three publication verifiers): **49,145** lines.

The earlier `32,260` figure was a narrower natural-selection-branch manifest,
not a total production-application count. It also omitted behavior-changing
feedback/strata code and the audited reporting evaluator, so it must not be
reported as total SAGE.

## Remaining execution gate

This release may be used to prepare the final ten-pair campaign only after the
tree is committed, clean, packaged, and passes the publication environment,
input, unit, integration, and no-secret checks. A live 1,032-task pair is not
part of code restoration and requires separate execution approval.
