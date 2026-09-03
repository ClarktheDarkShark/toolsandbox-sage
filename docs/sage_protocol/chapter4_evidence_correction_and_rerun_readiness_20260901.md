# Chapter 4 Evidence Correction and Rerun Readiness — 2026-09-01

## Decision

The July 2026 ten-online/ten-frozen campaign is preserved as an archival
development result but withdrawn as final inferential evidence. H1, H2, and H3
are pending replacement by a strict fresh-control ten-pair rerun. The
corrected-tree replacement sample has passed every release gate, and the
ten-pair manifest has been prepared and verified. No campaign arm may start
until the researcher gives explicit approval.

## Verified Correction

The baseline described as “v140” in the historical paper campaign was an
expanded hybrid cache, not the original one-record-per-task v140 snapshot.

| Property | Historical hybrid actually used | Original v140 sensitivity reference |
|---|---:|---:|
| Unique tasks | 1,032 | 1,032 |
| Complete records | 1,182 | 1,032 |
| Tasks with one record | 957 | 1,032 |
| Tasks with three records | 75 | 0 |
| Duplicate handling | Mean of compatible records | Not applicable |
| Outcome mean | 0.4573418739 | 0.4528026204750015 |

The extra 150 records came from later targeted control runs. For each of the 75
affected tasks, campaign lookup averaged three compatible records. The hybrid
values were used in two scientifically relevant places:

1. they supplied every reported matched control row in the ten online and ten
   frozen arms; and
2. the online self-evolution reflection controller read the same values when
   evaluating task outcomes and making lifecycle decisions.

The second point means this was not only an analysis-labeling problem. The
online system could make birth, retention, repair, or routing-related decisions
conditioned on hybrid cached comparisons. Consequently, replacing a column in
the final statistics cannot reconstruct the counterfactual strict
fresh-control campaign.

## Directional Sensitivity, Not Validation

The historical online SAGE outcome mean was `0.7954070629777463`. Holding that
value fixed and using the original v140 outcome mean gives:

```text
(0.7954070629777463 - 0.4528026204750015)
/ 0.4528026204750015
= 0.7566308741 (about 75.7%)
```

The corresponding historical hybrid-baseline headline was about 73.9%.
Therefore, the hybrid cache did not inflate the H2 relative-lift point estimate;
it raised the denominator and made that point estimate smaller. This check
supports only the direction of that narrow sensitivity statement. It does not
validate the historical intervals, randomization tests, run-level inference,
H1 gain retention, H3 mechanism attribution, or any online behavior influenced
by reflection.

The original v140 snapshot is frozen for historical sensitivity analysis and
is explicitly ineligible as a control source for new experiment runs. Its
content-addressed publication record is in the immutable
`docs/sage_protocol/publication_input_manifest_20260901.json`; the active
machine-verifiable chain is
`docs/sage_protocol/publication_release_manifest_20260902.json`.
The frozen checkpoint's clause proposing removal of generator analysis
memoization is superseded, without changing the checkpoint bytes, by
`docs/sage_protocol/publication_checkpoint_amendment_20260902.json`.

## Corrected Strict Fresh-Control Contract

Each new online or frozen arm must satisfy all of the following conditions:

- execute all 1,032 non-learning control tasks live before the SAGE condition;
- set control cache mode to `off` and never construct or read a
  `ControlBaselineCache`;
- disable SAGE task-result, persistent repository whole-response, and
  generated-output replay caches; preserve the validated generator's
  nonpersistent within-run contract-and-repair-analysis memoization; provider-managed
  prompt-prefix computation is recorded separately and does not replay a model
  response;
- require provider-prefix usage metadata for every model call and reconcile raw
  events exactly against per-task rows and arm summaries;
- reject diagnostic tool-exposure and force-call environment variables in both
  online and frozen publication arms, and require the independent verifier to
  confirm an empty active set;
- use exactly the same sealed 1,032-task manifest and order in both conditions;
- build online reflection input only from the just-completed same-run control;
- provide exactly one matching control row to each task reflection;
- fail closed on missing, duplicate, mismatched, extra, or unconsumed rows;
- start every online registry empty;
- copy only the completed paired online registry into its frozen run;
- disable generation, candidate repair, and online reflection in frozen mode;
- use the pinned RapidAPI response fixture in read-only mode and verify its
  SHA-256 before execution; this fixture is an external-service benchmark
  input, not a saved task result or model response;
- preserve complete command, environment, source, input, registry, task,
  comparison, and verification provenance.

The pinned public sanitized RapidAPI fixture SHA-256 is
`eae0a6ab7d2ee5dd272612a0b5ce44d85af34cd1297ff662007260941192322f`.
The semantically identical private capture from which it was sanitized is
separately pinned in the input manifest as
`4b3a8eca43fe8908330c7fc891597a8a418d3e109ff435726ec94e1177b2b05b`.
The benchmark SHA-256 is
`21877bd3524258b80f74207c66ed3640b6db629d13b4a2fb4d817e35d0390bec`.

## Evidence Status

| Evidence item | Permitted interpretation |
|---|---|
| July ten-pair point estimates and counts | Archival/descriptive only |
| Original-v140 substitution | Directional H2 point-estimate sensitivity only |
| Preserved July confidence intervals and tests | Superseded; not final inference |
| Corrected-tree replacement 1,032-task validation sample | Engineering integrity and predeclared outcome no-inferiority gate only |
| New strict fresh-control ten-pair campaign | Confirmatory evidence after all 20 arms verify |

A single complete validation sample cannot measure run-level stochastic
variation, provide ten independently evolved registries, support the planned
run-level sign-flip analysis, or accept/reject a hypothesis. It must remain in
a separate release-validation report and must not be pooled into the ten-pair
confirmatory dataset.

## Strict Validation Attempt Ledger

Sample 01 stopped in publication-environment preflight because its dependency
check failed. It created no experiment output files and made no model requests.
The tracked compact ledger entry is
`publication_validation_sample01_preflight_20260901.json`; its raw 1,971-byte
log is a local ignored artifact identified there by SHA-256.

## First Completed Strict-Intent Validation Attempt (Sample 02)

Sample 02 was the first completed strict-intent attempt: it completed all 1,032
control tasks and all 1,032 SAGE
tasks. The then-current integrity verification passed: the arms had identical ordered task
coverage, zero runtime exceptions, zero cached control rows, zero persistent
repository whole-response replay hits, and exact same-run fresh reflection mapping. OpenAI
usage metadata separately reported automatic provider prompt-prefix reuse;
those cached input tokens are not stored responses and were not controlled by
the removed SAGE caches.

The sample passed its outcome performance gates. Candidate outcome was
`0.7788122917`, above the historical minimum `0.7760515297`, and same-run
relative outcome lift was `58.04%`. The original v1 threshold incorrectly made
canonical/reference similarity a release gate. The researcher clarified on
2026-09-02 that outcome/task-completion similarity is the sole performance
endpoint; the active v2 thresholds make canonical descriptive only and are
content-addressed in the release chain.

A post-run code audit also found that the cleanup had removed the generator's
validated within-run contract-and-repair-analysis memoization. That changed the sequence
of model calls during repair and violated the explicit decision to defer
generator behavior. The memoization is nonpersistent and contains only analysis
created during the current generator lifetime; it does not import a prior-run
task result, model output, or campaign. It has been restored before any
replacement sample. Sample 02 therefore remains diagnostic evidence, not the
release gate for the corrected tree.

The audit also found that sample 02's launcher omitted the preserved July
campaign setting `SAGE_OPENAI_MAX_RETRIES=5`, causing the adapters to use their
default value of 2. The replacement release restores 5 and pins the complete
operational policy: both 1/3-second wrapper delay lists, four scenario attempts,
and 120/600-second request timeouts. This closes inherited-environment drift and
restores documented historical configuration before the replacement sample;
the separate outcome-only metric-policy correction is recorded explicitly in
the checkpoint amendment rather than being hidden as a retry decision.

## Corrected-Tree Validation Sample (Sample 03)

Sample 03 completed all 1,032 control tasks and all 1,032 SAGE tasks on the
corrected release tree. Across the 800 tasks with an explicit outcome
evaluator, mean outcome increased from `0.5087366331780064` to
`0.7986035515693737`, an absolute increase of `0.2898669183913673` and a
relative lift of `56.97779548144769%`. Exact outcome successes increased from
`220` to `443`; the paired outcome counts were `413` gains, `283` preserved,
and `104` regressions.

The strict verifier passed with complete `1,032/1,032` task coverage in both
arms, zero runtime exceptions, zero cached control tasks, zero repository
whole-response replay, and same-run-fresh reflection. The outcome-only
no-regression and same-run lift gates both passed. This is an engineering
validation result, not a confirmatory replication or a hypothesis decision.
The tracked record is `publication_validation_sample03_report.md`.

## Readiness and Approval Gates

Readiness before the final campaign is authorized:

1. **Complete:** source, environment, benchmark, RapidAPI fixture, analysis
   inputs, and publication manifests are frozen and verified.
2. **Complete:** static checks, retained unit/integration tests, and
   package-install smoke tests passed.
3. **Complete:** corrected-tree sample 03 finished both 1,032-task arms.
4. **Complete:** the strict verifier passed the integrity, lifecycle, and
   predeclared outcome-only gates.
5. **Complete:** sample 03 is recorded separately from Chapter 4 inference.
6. **Complete:** the ten-pair campaign manifest was prepared and verified
   without executing a campaign arm.
7. **Outstanding:** obtain explicit researcher approval before passing the
   campaign launcher's execution acknowledgement.

No failed or incomplete arm may be silently retried, excluded, or replaced.
Any failure must be preserved and reviewed before the campaign continues.

## Paper Replacement Rule

The current Chapter 4 tables and decisions remain marked historical until ten
new online and ten paired frozen arms pass the strict verifier. At that point,
the single-source analysis pipeline must regenerate all point estimates,
intervals, tests, lifecycle summaries, integrity findings, table images, and
hypothesis decisions from the new structured evidence input. No historical
inferential value may be copied forward manually.

## Decision Label

`READY_FOR_RESEARCHER_REVIEW: DO_NOT_EXECUTE_10_PAIR_CAMPAIGN_WITHOUT_EXPLICIT_APPROVAL`
