# H1, H3, and H4 Single-Run Viability With Completed Paper H2 (2026-09-20)

## Scope and correction

Execution ID: `h134_from_paper_h2_single_viability_20260920_01`.

This protocol follows `00_global_working_agreement.md` and supersedes only the
new September 19 pilot orchestration. It does not replace or modify the paper,
the paper H2 campaign, or any canonical Chapter 4 artifact. The incomplete IDs
`h134_paper_h2_10x_20260919_01` and `h134_single_viability_20260919_01` remain
preserved and ineligible; they are never resumed, repaired, or analyzed as
completed runs.

No new H2 model calls are permitted. H2 is the already completed and strictly
verified paper result: ten independently evolved SAGE registries, 10,320
matched task pairs, control mean 0.5862, SAGE mean 0.7835, relative lift
33.7%, and exact two-sided run-level sign-flip p=.001953125. Its canonical
selected-cohort manifest, verification receipt, and dashboard-data hashes are
pinned before H1 or H3 can begin.

Only H1, H3, and exploratory H4 receive new execution. This is a one-registry
engineering viability test, not a new confirmatory campaign.

## Locked hypotheses

- **H1:** Blind functional validity of accepted tools.
- **H2 (existing paper evidence):** Ten independently evolved SAGE registries
  outperform control.
- **H3:** Randomized availability of the frozen generated registry improves
  outcome over registry-masked SAGE.
- **H4 (exploratory backup):** A frozen registry built only on a randomized,
  disjoint discovery half improves outcome over registry-masked SAGE on the
  held-out half.

The primary task endpoint for H3 and H4 is the route-independent SAGE v9
outcome score. ToolSandbox canonical similarity is descriptive only.

## Deterministic paper-registry selection

H1 and H3 use replication 1 from the completed paper cohort because it is the
first strictly verified replication, not because of its observed outcome. Its
frozen registry has 28 active tools and one retired tool. The frozen registry
bytes, registry manifest, H2 control summary, selected-cohort manifest, and
selected-cohort verification are hash-pinned. H1 and H3 use the same immutable
registry identity.

The paper registry predates the later durable validation-contract file format.
Its original validation evidence is therefore recovered only through an
external, hash-pinned legacy-admission binding built deterministically from the
preserved replication-1 capability observations and `validation_passed` event
records. The extractor must match every active tool by exact name, version,
code hash, public-spec hash, and unique canonical validation-example set. It
must fail closed on missing, duplicate, or conflicting evidence. The external
binding never enters the assessor context and never modifies the frozen
registry. It is used only for exact admission-input overlap checking in H1 and
frozen-registry provenance preflight in H3.

## H1: blind functional validity

A separate-context assessor receives only the frozen public-spec scaffold and
content bindings—not generated code, admission examples, transcripts,
execution results, or the external legacy-admission binding. The assessor's
prompt, completion record, and completed case bank are preserved and hashed.
The case bank is sealed before the admission binding is supplied to the audit.

All 28 active, non-retired tools are in the denominator. Every tool receives
at least two unique exact-oracle cases. Native-action helpers must include at
least one positive exact native-call oracle and one negative/abstention oracle.
A tool passes only if all cases, static checks, content bindings, and
non-overlap checks pass. H1 clears this viability threshold only with at least
20 active tools, 100% coverage, at least 90% tool-weighted validity, immutable
registry bytes, zero admission-input overlap, and no critical unauthorized
native action.

## H3: randomized frozen-registry availability

H3 performs one fresh 1,032-task randomized-availability run using the
replication-1 frozen registry. Generation, repair, evaluator feedback,
reflection, and lifecycle mutation are disabled. The eight variants of each
original task stem share one assignment.

The locked replication-1 H2 control outcomes are pretreatment covariates. Seed
`20260918` forms 63 adjacent pairs plus one triplet and assigns 65 stems to
registry available and 64 to registry masked. The complete assignment,
external legacy-provenance receipt, and registry hash are sealed before the
first model request. Masked tasks retain the same policy wrapper and native
tools but must expose, attempt, and call zero generated tools.

The primary estimand is the 129-stem intention-to-treat difference, available
minus masked. H3 clears the viability threshold only with a positive estimate,
a one-sided restricted-randomization p-value below .05, a stem-cluster 95%
interval lower endpoint above zero, zero masked exposure, and unchanged source
and copied registries.

## H4: independent split-registry transfer test

H4 starts from a separate empty registry and consumes no paper registry. Seed
`20260919` with PCG64 locks 64 discovery stems (512 tasks) and 65 held-out
stems (520 tasks), with no stem split across halves. Discovery uses
`actor-visible-only` adaptation. It receives no hidden target, ToolSandbox
score, v9 outcome, or matched-control feedback.

After discovery, the registry is hash-bound and frozen. Two fresh concurrent
held-out arms compare registry available with registry masked. Generation,
repair, reflection, feedback, and mutation are disabled; the masked arm must
expose, attempt, and call zero generated tools. H4 clears its exploratory
threshold only with complete disjoint rosters, zero final exceptions,
immutable equal registry copies, zero masked exposure, relative lift of at
least 10%, and a paired 65-stem bootstrap interval lower endpoint above zero.

## Execution, concurrency, and monitoring

H1 must complete before H3 starts because both use the same paper registry and
H3 depends on the H1 integrity result. H4 is independent and may run in
parallel in a separate clean worktree and isolated publication environment.
This explicit researcher-authorized exception supersedes the global default
against overlapping phases without weakening any phase gate.

Durable launch receipts record the exact command, source commit/tree, process
identity, run root, log, and start time. Monitoring is stateful and must:

1. refuse duplicate launches or reuse of a failed/partial run ID;
2. verify exact process identity and task-count/log/result-file progress;
3. declare a stall only after at least 90 minutes without count or file growth
   across at least two checks;
4. never retry, resume, or repair a failed phase under the same ID;
5. on success, verify complete rosters, hashes, exposure gates, registry
   immutability, and result schema before recording the result;
6. start H3 only after a valid recorded H1 result;
7. refresh the established dashboard after every terminal transition; and
8. stop monitoring after H1, H3, and H4 are terminal, notifying only on
   completion, failure, stall, or required human action.

Decision label before execution: `READY_FOR_H1_H3_H4_SINGLE_VIABILITY`.
